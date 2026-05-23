import os
import shutil
import time
import datetime
import logging
import subprocess
import tempfile
from pathlib import Path
from app.core.config import settings
from app.core.celery import celery_app
from app.core.database import SessionLocal
from app.core.observability import agent_timer
from app.core.redis_events import publish_scan_event
from app.core.security import validate_git_url, redact_url_for_log
from app.models.models import Scan, Finding, AgentActivity
from app.services.agents.code_analyzer import CodeAnalyzerAgent
from app.services.agents.security_reviewer import SecurityReviewerAgent
from app.services.agents.threat_intel import ThreatIntelAgent
from app.services.agents.ml_agent import MLAgent

logger = logging.getLogger(__name__)


def _broadcast(scan_id: str, event: str, data: dict) -> None:
    """Publish scan event to Redis for WebSocket delivery in API process."""
    publish_scan_event(settings.REDIS_URL, scan_id, {"event": event, "data": data})


def _cleanup_workspace(target_path: str) -> None:
    """Remove ephemeral scan workspace directory after pipeline completes."""
    workspace = target_path
    if os.path.isfile(target_path):
        workspace = os.path.dirname(target_path)
    if not workspace or not os.path.isdir(workspace):
        return
    try:
        workspace_path = Path(workspace).resolve()
        root_path = Path(settings.SCAN_WORKSPACE_ROOT).resolve()
        if root_path not in workspace_path.parents and workspace_path != root_path:
            logger.error("Refusing to delete path outside scan workspace: %s", workspace_path)
            return
        shutil.rmtree(workspace_path, ignore_errors=True)
        logger.info("Cleaned up scan workspace: %s", workspace_path)
    except Exception as e:
        logger.exception(
            "Failed to clean scan workspace | path=%s | error=%s", workspace, e
        )


def _clone_repository(
    scan_id: str,
    git_url: str
) -> tuple[tempfile.TemporaryDirectory, str]:

    validated_url = validate_git_url(git_url)

    scan_root = (
        settings.SCAN_WORKSPACE_ROOT
        or "/tmp/cyberverse_scans"
    )

    # Create parent directory if missing
    os.makedirs(
        scan_root,
        exist_ok=True
    )

    logger.info(
        "Ensured scan workspace exists: %s",
        scan_root
    )

    temp_workspace = tempfile.TemporaryDirectory(
        prefix=f"{scan_id}_git_",
        dir=scan_root,
    )

    repo_path = os.path.join(
        temp_workspace.name,
        "repository"
    )

    git_exec = shutil.which("git") or "/usr/bin/git"

    safe_url = redact_url_for_log(
        validated_url
    )

    logger.info(
        "Cloning repository for scan_id=%s url=%s",
        scan_id,
        safe_url
    )

    try:
        subprocess.run(
            [
                git_exec,
                "clone",
                "--depth",
                str(settings.GIT_CLONE_DEPTH),
                "--",
                validated_url,
                repo_path
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.GIT_CLONE_TIMEOUT_SECONDS
        )

    except subprocess.TimeoutExpired as exc:
        temp_workspace.cleanup()
        raise TimeoutError(
            f"Git clone timed out after {settings.GIT_CLONE_TIMEOUT_SECONDS}s"
        ) from exc

    except subprocess.CalledProcessError as exc:
        temp_workspace.cleanup()

        logger.error(
            "Git clone failed: %s",
            (exc.stderr or "")[:500]
        )

        raise RuntimeError(
            "Failed to clone repository"
        ) from exc

    return temp_workspace, repo_path

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name="app.tasks.scan_tasks.run_scan_pipeline_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=120,
)
def run_scan_pipeline_task(self, scan_id: str, target_reference: str, target_type: str):
    """
    Celery task executing the multi-agent security scanning pipeline.
    Uses context-managed DB sessions, Redis WS bridge, and ephemeral workspace cleanup.
    """
    logger.info(
        "Celery task %s started | scan_id=%s | target=%s | type=%s",
        self.request.id, scan_id, redact_url_for_log(target_reference), target_type,
    )

    code_analyzer = CodeAnalyzerAgent()
    security_reviewer = SecurityReviewerAgent()
    threat_intel = ThreatIntelAgent()
    ml_agent = MLAgent()

    temp_workspace = None
    target_path = target_reference
    cleanup_after_task = True

    try:
        if target_type == "git":
            temp_workspace, target_path = _clone_repository(scan_id, target_reference)
        elif target_type == "code":
            if not os.path.exists(target_reference):
                raise FileNotFoundError("Staged scan target is missing")
        else:
            raise ValueError(f"Unsupported scan target type: {target_type}")

        with SessionLocal() as db:

            def push_activity_log(agent_name: str, message: str, log_type: str = "info"):
                try:
                    activity = AgentActivity(
                        scan_id=scan_id,
                        agent_name=agent_name,
                        message=message,
                        type=log_type,
                    )
                    db.add(activity)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.exception(
                        "Activity log DB write failed | scan_id=%s | agent=%s | error=%s",
                        scan_id, agent_name, e,
                    )
                _broadcast(scan_id, "log", {
                    "agent_name": agent_name,
                    "message": message,
                    "type": log_type,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                })

            def update_scan_status(phase: str, progress: int):
                try:
                    scan = db.query(Scan).filter(Scan.id == scan_id).first()
                    if scan:
                        scan.status = "running"
                        scan.current_phase = phase
                        scan.progress = progress
                        db.commit()
                except Exception as e:
                    db.rollback()
                    logger.exception(
                        "Scan status update failed | scan_id=%s | phase=%s | error=%s",
                        scan_id, phase, e,
                    )
                _broadcast(scan_id, "status", {
                    "scan_id": scan_id,
                    "phase": phase,
                    "progress": progress,
                })

            push_activity_log(
                "Orchestrator AI",
                f"Initialized scanning workflow for security target: {target_path}",
                "info",
            )
            update_scan_status("parsing", 15)
            push_activity_log(
                "Orchestrator AI",
                "Constructing AST maps and scanning high-entropy values...",
                "info",
            )

            with agent_timer(code_analyzer.name):
                findings = code_analyzer.analyze(target_path, scan_callback=push_activity_log)

            update_scan_status("analyzing", 40)
            push_activity_log(
                "Orchestrator AI",
                "Piping discovered code blocks to the Security Reviewer Agent...",
                "info",
            )
            with agent_timer(security_reviewer.name):
                reviewed_findings = security_reviewer.review_findings(
                    findings, scan_callback=push_activity_log
                )

            update_scan_status("enriching", 65)
            push_activity_log(
                "Orchestrator AI",
                "Piping findings to Threat Intelligence Agent for CVE and MITRE mapping...",
                "info",
            )
            with agent_timer(threat_intel.name):
                enriched_findings = threat_intel.enrich_findings(
                    reviewed_findings, scan_callback=push_activity_log
                )

            update_scan_status("scoring", 85)
            push_activity_log(
                "Orchestrator AI",
                "Running Machine Learning risk classifier models...",
                "info",
            )
            with agent_timer(ml_agent.name):
                ml_profile = ml_agent.assess_risk(
                    enriched_findings, target_path, scan_callback=push_activity_log
                )

            try:
                db.query(Finding).filter(Finding.scan_id == scan_id).delete()

                for f in enriched_findings:
                    finding_obj = Finding(
                        scan_id=scan_id,
                        title=f["title"],
                        description=f["description"],
                        severity=f["severity"],
                        file_path=f.get("file_path"),
                        line_number=f.get("line_number"),
                        code_snippet=f.get("code_snippet"),
                        cwe=f.get("cwe"),
                        cve=f.get("cve"),
                        mitre_attack=f.get("mitre_attack"),
                        owasp_category=f.get("owasp_category"),
                        confidence=f.get("confidence"),
                        package=f.get("package"),
                        current_version=f.get("current_version"),
                        fixed_version=f.get("fixed_version"),
                        remediation_explanation=f.get("remediation_explanation"),
                        remediation_code=f.get("remediation_code"),
                    )
                    db.add(finding_obj)

                scan = db.query(Scan).filter(Scan.id == scan_id).first()
                if scan:
                    scan.status = "completed"
                    scan.risk_score = ml_profile["risk_score"]
                    scan.critical_count = ml_profile["critical_count"]
                    scan.high_count = ml_profile["high_count"]
                    scan.medium_count = ml_profile["medium_count"]
                    scan.low_count = ml_profile["low_count"]
                    scan.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    scan.current_phase = "done"
                    scan.progress = 100

                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception(
                    "DB error storing findings | scan_id=%s | error=%s", scan_id, e
                )
                raise

            push_activity_log(
                "Orchestrator AI",
                "Pipeline successfully completed. Export models are compiled and ready.",
                "success",
            )
            _broadcast(scan_id, "completed", {
                "scan_id": scan_id,
                "risk_score": ml_profile["risk_score"],
                "critical_count": ml_profile["critical_count"],
                "high_count": ml_profile["high_count"],
                "medium_count": ml_profile["medium_count"],
                "low_count": ml_profile["low_count"],
            })

    except Exception as err:
        logger.exception(
            "Scan pipeline execution failed | scan_id=%s | error=%s", scan_id, err
        )
        try:
            with SessionLocal() as db:
                scan = db.query(Scan).filter(Scan.id == scan_id).first()
                if scan:
                    scan.status = "failed"
                    scan.current_phase = "failed"
                    db.commit()
                activity = AgentActivity(
                    scan_id=scan_id,
                    agent_name="Orchestrator AI",
                    message=f"Pipeline execution failed: {str(err)}",
                    type="error",
                )
                db.add(activity)
                db.commit()
        except Exception as e:
            logger.exception(
                "Failed to mark scan as failed | scan_id=%s | error=%s", scan_id, e
            )

        _broadcast(scan_id, "failed", {"scan_id": scan_id, "error": str(err)})

        try:
            if self.request.retries < (getattr(self, "max_retries", 0) or 0):
                cleanup_after_task = target_type == "git"
            raise self.retry(exc=err)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for scan %s", scan_id)

    finally:
        if not cleanup_after_task:
            logger.info(
                "Preserving staged scan workspace for retry | scan_id=%s | type=%s",
                scan_id,
                target_type,
            )
        elif temp_workspace is not None:
            temp_workspace.cleanup()
            logger.info("Cleaned up git scan workspace | scan_id=%s", scan_id)
        else:
            _cleanup_workspace(target_path)
