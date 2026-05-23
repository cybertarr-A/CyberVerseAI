import os
import shutil
import uuid
import datetime
import asyncio
import io
import logging
import json
import time
import tempfile
import contextvars
import re
from enum import Enum
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field, field_validator

# ----------------- Structured Logging -----------------
_request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_SENSITIVE_LOG_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key|token|secret|password)(\s*[=:]\s*)[^,\s]+"),
    re.compile(r"(https?://)([^/@\s]+)@"),
)


def _redact_log_value(value: str) -> str:
    redacted = value
    redacted = _SENSITIVE_LOG_PATTERNS[0].sub(r"\1[REDACTED]", redacted)
    redacted = _SENSITIVE_LOG_PATTERNS[1].sub(r"\1\2[REDACTED]", redacted)
    redacted = _SENSITIVE_LOG_PATTERNS[2].sub(r"\1[REDACTED]@", redacted)
    return redacted


class StructuredJSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "message": _redact_log_value(record.getMessage()),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno
        }
        if record.exc_info:
            log_record["exception"] = _redact_log_value(self.formatException(record.exc_info))
        request_id = getattr(record, "request_id", None) or _request_id_ctx.get()
        if request_id:
            log_record["request_id"] = request_id
        for attr in ("scan_id", "agent", "file"):
            value = getattr(record, attr, None)
            if value:
                log_record[attr] = value
        return json.dumps(log_record)

# Configure the root logger with the Structured JSON Formatter
json_handler = logging.StreamHandler()
json_handler.setFormatter(StructuredJSONFormatter())
logging.getLogger().handlers = [json_handler]
logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ----------------- Application Imports -----------------
from app.core.config import settings
from app.core.database import get_db
from app.core.migrations import initialize_database
from app.core.rate_limiter import create_rate_limiter
from app.core.observability import (
    MetricsCollector,
    setup_tracing,
    prometheus_metrics,
    update_system_metrics,
    update_queue_metrics,
    PROMETHEUS_AVAILABLE,
)
from app.core.redis_events import ScanEventSubscriber
from app.models.models import Project, Scan, Finding, AgentActivity
from app.services.agents.orchestrator import OrchestratorAgent, ws_manager
from app.core.security import (
    sanitize_filename,
    validate_scan_id,
    validate_git_url,
    redact_url_for_log,
)
from pathlib import Path
from app.tasks.scan_tasks import run_scan_pipeline_task

api_rate_limiter = create_rate_limiter(
    redis_url=settings.REDIS_URL,
    rate=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    redis_required=settings.RATE_LIMIT_REDIS_REQUIRED,
)
metrics = MetricsCollector()
scan_event_subscriber = ScanEventSubscriber(settings.REDIS_URL, ws_manager)
STARTED_AT = time.monotonic()

# ----------------- Lifespan (replaces deprecated on_event) -----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle manager."""
    logger.info("CyberVerse AI starting up — initializing background services")
    setup_tracing("cyberverse-api")
    initialize_database()

    background_tasks: list[asyncio.Task] = []
    heartbeat_task = asyncio.create_task(ws_manager.run_heartbeat_sweep())
    rate_cleanup_task = asyncio.create_task(_rate_limiter_cleanup_loop())
    background_tasks.extend([heartbeat_task, rate_cleanup_task])

    await scan_event_subscriber.start()

    yield

    logger.info("CyberVerse AI shutting down — cleaning up resources")
    await scan_event_subscriber.stop()
    await ws_manager.cancel_pending_tasks()
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

async def _rate_limiter_cleanup_loop():
    """Periodically clean stale rate limiter buckets."""
    while True:
        await asyncio.sleep(300)
        await api_rate_limiter.cleanup_stale_buckets()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CyberVerse AI Multi-Agent Cybersecurity Intelligence Center API",
    version="1.0.0",
    lifespan=lifespan,
)

# ----------------- CORS Middleware -----------------

# Read origins from environment:
# CORS_ORIGINS=https://cyber-verse-ai.vercel.app,http://localhost:3000

cors_origins = settings.CORS_ORIGINS

if isinstance(
    cors_origins,
    str
):
    allowed_origins = [
        origin.strip()
        for origin in cors_origins.split(",")
        if origin.strip()
    ]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://cyber-verse-ai.vercel.app"
    ]

logger.info(
    "Configured CORS origins: %s",
    allowed_origins
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-Response-Time-Ms",
    ]
)
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Combined middleware: request ID injection, rate limiting, structured logging, and metrics."""
    # Inject unique request ID for distributed tracing
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = _request_id_ctx.set(request_id)
    try:
        # Rate limit /api/v1/ REST API paths
        if request.url.path.startswith("/api/v1/"):
            client_ip = request.client.host if request.client else "unknown"
            if not await api_rate_limiter.allow_request(client_ip):
                logger.warning(
                    "Rate limit exceeded for IP %s on %s", client_ip, request.url.path
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "message": "API rate limit exceeded. Please try again later.",
                        "request_id": request_id,
                    },
                    headers={"X-Request-ID": request_id},
                )

        start_time = time.monotonic()
        response = await call_next(request)
        latency_ms = (time.monotonic() - start_time) * 1000

        # Inject tracing headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{latency_ms:.2f}"

        # Structured request log
        logger.info(
            "HTTP %s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
        )

        # Record metrics
        await metrics.record_request(
            request.method, request.url.path, response.status_code, latency_ms
        )

        return response
    finally:
        _request_id_ctx.reset(token)

# Initialize Orchestrator Agent
orchestrator = OrchestratorAgent()

# Ephemeral scan workspace root (per-scan subdirs are created and cleaned by Celery)
SCAN_WORKSPACE_ROOT = (
    settings.SCAN_WORKSPACE_ROOT
    or "/tmp/cyberverse_scans"
)

os.makedirs(
    SCAN_WORKSPACE_ROOT,
    exist_ok=True
)

logger.info(
    "Scan workspace initialized: %s",
    SCAN_WORKSPACE_ROOT
)


def _cleanup_scan_workspace(workspace: str) -> None:
    try:
        workspace_path = Path(workspace).resolve()
        root_path = Path(SCAN_WORKSPACE_ROOT).resolve()
        if root_path not in workspace_path.parents and workspace_path != root_path:
            logger.error("Refusing to clean path outside scan workspace: %s", workspace_path)
            return
        shutil.rmtree(workspace_path, ignore_errors=True)
    except Exception as exc:
        logger.exception("Scan workspace cleanup failed: %s", exc)


def _write_upload_to_path(upload: UploadFile, destination: Path) -> int:
    total = 0
    chunk_size = 1024 * 1024
    with destination.open("wb") as output:
        while True:
            chunk = upload.file.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > settings.MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Uploaded file exceeds {settings.MAX_UPLOAD_BYTES} byte limit",
                )
            output.write(chunk)
    return total

# =====================================================================
# Health, Readiness, and Metrics Endpoints
# =====================================================================

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Deep health check: verifies database connectivity, disk availability,
    and returns subsystem statuses for monitoring dashboards.
    """
    checks = {}
    overall_healthy = True

    # Database connectivity
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy", "backend": settings.DATABASE_URL.split("://")[0]}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False

    # Disk space for scan workspace
    try:
        stat = os.statvfs(SCAN_WORKSPACE_ROOT)
        free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
        checks["disk"] = {"status": "healthy" if free_gb > 1.0 else "warning", "free_gb": round(free_gb, 2)}
        if free_gb < 0.5:
            overall_healthy = False
    except Exception as e:
        logger.exception("Disk health check failed: %s", e)
        checks["disk"] = {"status": "unknown", "error": str(e)}

    # Celery broker connectivity
    try:
        from app.core.celery import celery_app
        inspector = celery_app.control.inspect(timeout=2.0)
        active_workers = inspector.ping()
        checks["celery"] = {
            "status": "healthy" if active_workers else "degraded",
            "workers": len(active_workers) if active_workers else 0,
        }
    except Exception as e:
        logger.exception("Celery health check failed: %s", e)
        checks["celery"] = {"status": "unavailable", "workers": 0}

    # WebSocket manager and system metrics
    checks["websockets"] = ws_manager.metrics
    
    try:
        checks["queue"] = update_queue_metrics(settings.REDIS_URL, settings.CELERY_QUEUE_NAME)
    except Exception as e:
        logger.exception("Queue metrics update failed: %s", e)
        checks["queue"] = {"status": "unavailable"}

    try:
        checks["system"] = update_system_metrics(
            ws_connections=ws_manager.metrics.get("active_connections", 0),
            active_scans=metrics.active_scans,
        )
    except Exception as e:
        logger.exception("System metrics update failed: %s", e)
        checks["system"] = {"status": "unavailable"}

    return JSONResponse(
        status_code=200 if overall_healthy else 503,
        content={
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "version": "1.0.0",
            "checks": checks,
        },
    )

@app.get("/ready")
def readiness_probe(db: Session = Depends(get_db)):
    """Lightweight readiness probe for container orchestration (K8s, Docker)."""
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        logger.exception("Readiness probe failed: %s", e)
        return JSONResponse(status_code=503, content={"ready": False})


@app.get("/readiness")
def readiness_probe_alias(db: Session = Depends(get_db)):
    """Kubernetes-style readiness endpoint alias."""
    return readiness_probe(db)


@app.get("/liveness")
def liveness_probe():
    """Liveness probe — process is running and accepting requests."""
    return {
        "alive": True,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """JSON metrics snapshot for dashboards."""
    metrics.active_scans = (
        db.query(func.count(Scan.id))
        .filter(Scan.status.in_(["pending", "running"]))
        .scalar()
        or 0
    )
    snapshot = await metrics.snapshot()
    snapshot["websockets"] = ws_manager.metrics
    snapshot["queue"] = update_queue_metrics(settings.REDIS_URL, settings.CELERY_QUEUE_NAME)
    snapshot["system"] = update_system_metrics(
        ws_connections=ws_manager.metrics.get("active_connections", 0),
        active_scans=metrics.active_scans,
    )
    return snapshot


@app.get("/metrics/prometheus")
def prometheus_endpoint():
    """Prometheus text exposition format for scraping."""
    if not PROMETHEUS_AVAILABLE:
        return JSONResponse(
            status_code=503,
            content={"error": "prometheus_client not installed"},
        )
    content, content_type = prometheus_metrics()
    return Response(content=content, media_type=content_type)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

# =====================================================================
# Projects API
# =====================================================================

@app.get("/api/v1/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).all()
    # If no projects exist, seed a default one
    if not projects:
        default_proj = Project(
            name="Default Sandbox Target",
            description="Default workspace sandbox to audit local repositories, codes, and vulnerabilities."
        )
        db.add(default_proj)
        db.commit()
        db.refresh(default_proj)
        projects = [default_proj]
    return projects

class ProjectCreateSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the project")
    description: str = Field("", max_length=500, description="Optional description")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Reject names with shell metacharacters or control characters."""
        import re
        if not re.match(r"^[a-zA-Z0-9 _\-\.]+$", v.strip()):
            raise ValueError("Project name contains invalid characters. Use letters, numbers, spaces, hyphens, underscores, dots only.")
        return v.strip()

@app.post("/api/v1/projects")
def create_project(payload: ProjectCreateSchema, db: Session = Depends(get_db)):
    existing = db.query(Project).filter(Project.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project with this name already exists")
    
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

# =====================================================================
# Scans API
# =====================================================================

class ReportFormat(str, Enum):
    json = "json"
    markdown = "markdown"
    pdf = "pdf"

@app.get("/api/v1/scans")
def list_scans(db: Session = Depends(get_db)):
    return db.query(Scan).order_by(Scan.created_at.desc()).all()

@app.get("/api/v1/scans/{scan_id}")
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    # Validate scan_id format
    try:
        scan_id = validate_scan_id(scan_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan session not found")
    
    findings = db.query(Finding).filter(Finding.scan_id == scan_id).all()
    activities = db.query(AgentActivity).filter(AgentActivity.scan_id == scan_id).order_by(AgentActivity.timestamp.asc()).all()
    
    return {
        "scan": scan,
        "findings": findings,
        "activities": activities
    }

@app.post("/api/v1/scans/file")
async def start_file_scan(
    project_id: int = Form(..., ge=1, description="Project ID"),
    target_name: str = Form(..., min_length=1, max_length=255, description="Target filename"),
    code_content: str = Form(None, max_length=1_000_000, description="Pasted code content"),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    """Initiate scan using direct pasted code contents or an uploaded single file."""
    # Verify project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scan_uuid = str(uuid.uuid4())
    
    # Sanitize and validate filename to block path traversal, null-bytes, and command/shell injections
    try:
        safe_name = sanitize_filename(Path(target_name).name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Security Validation Failed: {str(e)}")

    if not code_content and not file:
        raise HTTPException(status_code=400, detail="Either code_content or a file upload is required")

    if code_content and len(code_content.encode("utf-8")) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Code content exceeds {settings.MAX_UPLOAD_BYTES} byte limit",
        )

    scan_workspace = tempfile.mkdtemp(prefix=f"{scan_uuid}_", dir=SCAN_WORKSPACE_ROOT)
    scan_path = Path(scan_workspace) / safe_name

    # Check paste content vs upload file
    try:
        if code_content:
            scan_path.write_text(code_content, encoding="utf-8")
        elif file:
            _write_upload_to_path(file, scan_path)
    except HTTPException:
        _cleanup_scan_workspace(scan_workspace)
        raise
    except Exception as exc:
        _cleanup_scan_workspace(scan_workspace)
        logger.exception(
            "Failed to stage uploaded scan target | scan_id=%s | file=%s | error=%s",
            scan_uuid,
            safe_name,
            exc,
        )
        raise HTTPException(status_code=500, detail="Failed to stage scan target")

    # Create scan row
    scan = Scan(
        id=scan_uuid,
        project_id=project_id,
        status="pending",
        target_type="code",
        target_value=safe_name,
        progress=0,
        current_phase="idle"
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Enqueue production Celery task queue pipeline
    try:
        run_scan_pipeline_task.apply_async(
            args=[scan_uuid, str(scan_path), "code"],
            task_id=scan_uuid,
            queue=settings.CELERY_QUEUE_NAME,
        )
    except Exception as exc:
        queued_scan = db.query(Scan).filter(Scan.id == scan_uuid).first()
        if queued_scan:
            queued_scan.status = "failed"
            queued_scan.current_phase = "failed"
            db.commit()
        _cleanup_scan_workspace(scan_workspace)
        logger.exception("Failed to enqueue file scan | scan_id=%s | error=%s", scan_uuid, exc)
        raise HTTPException(status_code=503, detail="Scan queue is unavailable")

    await metrics.record_request("SCAN", "/api/v1/scans/file", 200, 0)
    metrics.scan_count += 1
    metrics.active_scans += 1
    logger.info("File scan dispatched: scan_id=%s, target=%s", scan_uuid, safe_name)

    return {"scan_id": scan_uuid, "status": "pending"}

@app.post("/api/v1/scans/git")
async def start_git_scan(
    project_id: int = Form(..., ge=1, description="Project ID"),
    git_url: str = Form(..., min_length=10, max_length=2048, description="Git repository URL"),
    db: Session = Depends(get_db)
):
    """Initiate scan against a Git URL."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # SECURITY: Validate Git URL before passing to subprocess
    try:
        validated_url = validate_git_url(git_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    scan_uuid = str(uuid.uuid4())

    # Create scan row
    scan = Scan(
        id=scan_uuid,
        project_id=project_id,
        status="pending",
        target_type="git",
        target_value=validated_url,
        progress=0,
        current_phase="idle"
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Enqueue production Celery task queue pipeline. The worker performs clone
    # and cleanup so slow network IO never blocks the API process.
    try:
        run_scan_pipeline_task.apply_async(
            args=[scan_uuid, validated_url, "git"],
            task_id=scan_uuid,
            queue=settings.CELERY_QUEUE_NAME,
        )
    except Exception as exc:
        scan.status = "failed"
        scan.current_phase = "failed"
        db.commit()
        logger.exception("Failed to enqueue git scan | scan_id=%s | error=%s", scan_uuid, exc)
        raise HTTPException(status_code=503, detail="Scan queue is unavailable")

    await metrics.record_request("SCAN", "/api/v1/scans/git", 200, 0)
    metrics.scan_count += 1
    metrics.active_scans += 1
    logger.info(
        "Git scan dispatched: scan_id=%s, url=%s",
        scan_uuid,
        redact_url_for_log(validated_url),
    )

    return {"scan_id": scan_uuid, "status": "pending"}

@app.get("/api/v1/scans/{scan_id}/status")
def get_scan_task_status(scan_id: str, db: Session = Depends(get_db)):
    """
    Exposes Celery task execution state, database progress metadata, and failure tracking.
    """
    try:
        scan_id = validate_scan_id(scan_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    from celery.result import AsyncResult
    from app.core.celery import celery_app
    
    celery_status = None
    task_error = None
    
    try:
        res = AsyncResult(scan_id, app=celery_app)
        celery_status = res.status
        if res.failed():
            task_error = str(res.result)
    except Exception as e:
        logger.warning("Could not fetch Celery AsyncResult for scan_id %s: %s", scan_id, e)

    return {
        "scan_id": scan_id,
        "status": scan.status,
        "current_phase": scan.current_phase,
        "progress": scan.progress,
        "celery_status": celery_status or "UNKNOWN",
        "error": task_error,
        "risk_score": scan.risk_score,
        "counts": {
            "critical": scan.critical_count,
            "high": scan.high_count,
            "medium": scan.medium_count,
            "low": scan.low_count
        }
    }

# =====================================================================
# Reports Export API
# =====================================================================

@app.get("/api/v1/scans/{scan_id}/report/{report_format}")
def export_scan_report(scan_id: str, report_format: ReportFormat, db: Session = Depends(get_db)):
    try:
        scan_id = validate_scan_id(scan_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    findings = db.query(Finding).filter(Finding.scan_id == scan_id).all()
    
    findings_list = []
    for f in findings:
        findings_list.append({
            "title": f.title,
            "description": f.description,
            "severity": f.severity,
            "file_path": f.file_path,
            "line_number": f.line_number,
            "code_snippet": f.code_snippet,
            "cwe": f.cwe,
            "cve": f.cve,
            "mitre_attack": f.mitre_attack,
            "owasp_category": f.owasp_category,
            "remediation_explanation": f.remediation_explanation,
            "remediation_code": f.remediation_code,
            "confidence": f.confidence or "Medium",
            "package": f.package,
            "current_version": f.current_version,
            "fixed_version": f.fixed_version,
        })
        
    scan_dict = {
        "id": scan.id,
        "status": scan.status,
        "target_value": scan.target_value,
        "risk_score": scan.risk_score,
        "critical_count": scan.critical_count,
        "high_count": scan.high_count,
        "medium_count": scan.medium_count,
        "low_count": scan.low_count,
        "created_at": scan.created_at
    }

    if report_format == ReportFormat.json:
        report_data = orchestrator.report_agent.generate_json_report(scan_dict, findings_list)
        return JSONResponse(content=report_data)
        
    elif report_format == ReportFormat.markdown:
        report_md = orchestrator.report_agent.generate_markdown_report(scan_dict, findings_list)
        return Response(content=report_md, media_type="text/markdown", headers={
            "Content-Disposition": f"attachment; filename=cyberverse_report_{scan_id}.md"
        })
        
    elif report_format == ReportFormat.pdf:
        report_pdf_bytes = orchestrator.report_agent.generate_pdf_report(scan_dict, findings_list)
        return StreamingResponse(
            io.BytesIO(report_pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=cyberverse_report_{scan_id}.pdf"}
        )

# =====================================================================
# System Telemetry API
# =====================================================================

@app.get("/api/v1/telemetry")
def get_dashboard_telemetry(db: Session = Depends(get_db)):
    """Retrieves high-level dashboard visualization statistics using efficient aggregate queries."""
    total_projects = db.query(func.count(Project.id)).scalar() or 0
    total_scans = db.query(func.count(Scan.id)).scalar() or 0
    
    # Aggregate vulnerability counts using SQL rather than loading all scans into memory
    vuln_counts = db.query(
        func.coalesce(func.sum(Scan.critical_count), 0),
        func.coalesce(func.sum(Scan.high_count), 0),
        func.coalesce(func.sum(Scan.medium_count), 0),
        func.coalesce(func.sum(Scan.low_count), 0),
    ).first()
    
    total_critical, total_high, total_medium, total_low = vuln_counts

    # Average risk score for completed scans
    avg_risk = db.query(func.avg(Scan.risk_score)).filter(Scan.status == "completed").scalar() or 0.0
    avg_risk = round(float(avg_risk), 1)
    
    # Active scanning count
    active_scanning = db.query(func.count(Scan.id)).filter(Scan.status.in_(["pending", "running"])).scalar() or 0
    
    # Recent findings summary
    recent_findings = db.query(Finding).order_by(Finding.created_at.desc()).limit(5).all()

    queue_metrics = {}
    system_metrics = {}

    try:
        queue_metrics = update_queue_metrics(settings.REDIS_URL, settings.CELERY_QUEUE_NAME)
    except Exception:
        queue_metrics = {
            "status": "unavailable"
        }

    try:
        system_metrics = update_system_metrics(
            ws_connections=ws_manager.metrics.get("active_connections", 0),
            active_scans=active_scanning,
        )
    except Exception:
        system_metrics = {
            "status": "unavailable"
        }

    return {
        "stats": {
            "projects": total_projects,
            "scans": total_scans,
            "avg_risk": avg_risk,
            "active_scanning": active_scanning
        },
        "vulnerability_counts": {
            "Critical": int(total_critical),
            "High": int(total_high),
            "Medium": int(total_medium),
            "Low": int(total_low)
        },
        "recent_findings": [{
            "id": f.id,
            "title": f.title,
            "severity": f.severity,
            "file": f.file_path,
            "cwe": f.cwe,
            "cve": f.cve
        } for f in recent_findings],
        "queue": queue_metrics,
        "system": system_metrics,
        "uptime_seconds": int(time.monotonic() - STARTED_AT),
    }

# =====================================================================
# WebSockets
# =====================================================================

@app.websocket("/ws/scan/{scan_id}")
async def websocket_endpoint(websocket: WebSocket, scan_id: str):
    try:
        scan_id = validate_scan_id(scan_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    ws_manager.register(scan_id, websocket)
    try:
        while True:
            # Sockets stream scanner outputs, so we wait for connection closure
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.unregister(scan_id, websocket)
    except Exception as e:
        ws_manager.unregister(scan_id, websocket)
        logger.exception("WebSocket error for scan_id %s: %s", scan_id, e)

@app.get("/api/v1/telemetry/ws")
async def get_websocket_telemetry():
    """Retrieves current websocket capacity and health indicators."""
    return ws_manager.metrics
