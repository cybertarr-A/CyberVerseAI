import os
import shutil
import time
import datetime
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from celery import group, chord
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
from app.services.chunker import RepositoryChunker
from app.services.result_merger import ResultMerger
from app.tasks.analysis_tasks import analyze_chunk

logger = logging.getLogger("cyberverse.scan_tasks")


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
    scan_root = settings.SCAN_WORKSPACE_ROOT or "/tmp/cyberverse_scans"

    os.makedirs(scan_root, exist_ok=True)
    logger.info("Ensured scan workspace exists: %s", scan_root)

    temp_workspace = tempfile.TemporaryDirectory(
        prefix=f"{scan_id}_git_",
        dir=scan_root,
    )

    repo_path = os.path.join(temp_workspace.name, "repository")
    git_exec = shutil.which("git") or "/usr/bin/git"
    safe_url = redact_url_for_log(validated_url)

    logger.info("Cloning repository for scan_id=%s url=%s", scan_id, safe_url)

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
        logger.error("Git clone failed: %s", (exc.stderr or "")[:500])
        raise RuntimeError("Failed to clone repository") from exc

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
    Celery task executing the initial steps of the scanning pipeline.
    Parses and chunks codebase, then dispatches non-blocking parallel tasks.
    """
    logger.info(
        "Celery run_scan_pipeline_task started | scan_id=%s | target=%s",
        scan_id, redact_url_for_log(target_reference)
    )

    temp_workspace = None
    target_path = target_reference
    temp_workspace_path = None

    try:
        if target_type == "git":
            temp_workspace, target_path = _clone_repository(scan_id, target_reference)
            temp_workspace_path = temp_workspace.name
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
                        "Activity log DB write failed | scan_id=%s | agent=%s",
                        scan_id, agent_name
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
                        "Scan status update failed | scan_id=%s | phase=%s",
                        scan_id, phase
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
            update_scan_status("parsing", 20)
            push_activity_log(
                "Orchestrator AI",
                "Initiating codebase recursive chunking and formatting filters...",
                "info",
            )

            chunks = RepositoryChunker.chunk_repository(target_path)
            logger.info("Chunk count: %d", len(chunks))
            push_activity_log(
                "Orchestrator AI",
                f"Completed codebase chunking. Generated {len(chunks)} chunks for parallel analysis.",
                "info",
            )

            if chunks:
                update_scan_status("analyzing", 45)
                push_activity_log(
                    "Orchestrator AI",
                    f"Spawning {len(chunks)} parallel Celery chunk analysis tasks...",
                    "info",
                )

                # Formulate a Celery chord to process chunks in parallel and aggregate asynchronously
                header = group(analyze_chunk.s(chunk) for chunk in chunks)
                callback = aggregate_scan_results.s(
                    scan_id=scan_id,
                    temp_workspace_path=temp_workspace_path,
                    target_path=target_path,
                    total_chunks=len(chunks)
                )
                
                # Execute the workflow asynchronously (non-blocking)
                chord(header)(callback)
                logger.info("Asynchronous Celery chord successfully dispatched for scan %s.", scan_id)
            else:
                push_activity_log(
                    "Orchestrator AI",
                    "No supported target code files found in the repository.",
                    "warning",
                )
                # Dispatch aggregation with empty results directly
                aggregate_scan_results.apply_async(
                    args=([], scan_id),
                    kwargs={
                        "temp_workspace_path": temp_workspace_path,
                        "target_path": target_path,
                        "total_chunks": 0
                    }
                )

    except Exception as err:
        logger.exception("Scan pipeline setup failed | scan_id=%s", scan_id)
        
        # Clean up temporary workspaces on immediate errors
        if temp_workspace is not None:
            temp_workspace.cleanup()
        else:
            _cleanup_workspace(target_path)

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
            logger.exception("Failed to mark scan as failed in DB | scan_id=%s", scan_id)

        _broadcast(scan_id, "failed", {"scan_id": scan_id, "error": str(err)})
        raise self.retry(exc=err)


@celery_app.task(
    name="app.tasks.scan_tasks.aggregate_scan_results",
    bind=True,
    max_retries=3,
    default_retry_delay=15
)
def aggregate_scan_results(
    self,
    results: List[Dict[str, Any]],
    scan_id: str,
    temp_workspace_path: Optional[str] = None,
    target_path: Optional[str] = None,
    total_chunks: int = 0
):
    """
    Decoupled callback task that aggregates, consolidates, and enriches
    individual chunk scan outcomes, writes to DB, and cleans workspace.
    """
    logger.info(
        "START: Aggregating scan results for scan_id=%s | total_chunks=%d",
        scan_id, total_chunks
    )
    start_time = time.time()

    all_security = []
    all_architecture = []
    all_quality = []
    all_performance = []
    all_recommendations = []
    failed_chunks = 0

    try:
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
                    logger.exception("Activity log DB write failed in callback | scan_id=%s", scan_id)
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
                    logger.exception("Scan status update failed in callback | scan_id=%s", scan_id)
                _broadcast(scan_id, "status", {
                    "scan_id": scan_id,
                    "phase": phase,
                    "progress": progress,
                })

            # Compile parallel chunk analysis results
            for idx, r in enumerate(results, 1):
                if not isinstance(r, dict) or r.get("status") != "success":
                    failed_chunks += 1
                    logger.warning("Chunk %d failed to analyze cleanly: %s", idx, r.get("error", "Unknown error"))
                    continue
                
                data = r.get("data", {})
                if isinstance(data, dict):
                    all_security.extend(data.get("security_findings") or [])
                    all_architecture.extend(data.get("architecture_issues") or [])
                    all_quality.extend(data.get("code_quality") or [])
                    all_performance.extend(data.get("performance_concerns") or [])
                    all_recommendations.extend(data.get("recommendations") or [])

            # Hybrid Multi-Agent Enrichment
            final_security = all_security
            if all_security:
                try:
                    security_reviewer = SecurityReviewerAgent()
                    threat_intel = ThreatIntelAgent()

                    push_activity_log(
                        "Threat Intelligence Agent",
                        f"Enriching {len(all_security)} discovered security vulnerability findings...",
                        "info"
                    )
                    enriched_security = threat_intel.enrich_findings(all_security, push_activity_log)
                    
                    push_activity_log(
                        "Security Review Agent",
                        "OWASP Top 10 category mapping and secure remediation generation active...",
                        "info"
                    )
                    final_security = security_reviewer.review_findings(enriched_security, push_activity_log)
                except Exception as enrichment_err:
                    logger.exception("Multi-agent enrichment encountered an error, falling back to raw findings: %s", enrichment_err)
                    push_activity_log(
                        "Orchestrator AI",
                        "Enrichment pipeline completed with warnings. Saving raw findings to DB.",
                        "warning"
                    )

            # Consolidate and compile dynamic Markdown threat reports
            update_scan_status("enriching", 75)
            push_activity_log(
                "Orchestrator AI",
                "Consolidating parallel chunk results and generating dynamic Markdown threat report...",
                "info",
            )
            merged_report = ResultMerger.merge_results(results, failed_chunks, total_chunks)

            # Risk Calculations
            critical_count = sum(1 for f in final_security if str(f.get("severity")).lower() == "critical")
            high_count = sum(1 for f in final_security if str(f.get("severity")).lower() == "high")
            medium_count = sum(1 for f in final_security if str(f.get("severity")).lower() == "medium")
            low_count = sum(1 for f in final_security if str(f.get("severity")).lower() == "low")
            
            base_score = float(critical_count * 25 + high_count * 15 + medium_count * 8 + low_count * 3)
            risk_score = min(100.0, base_score)

            update_scan_status("scoring", 90)
            push_activity_log(
                "Orchestrator AI",
                f"Scan risk profile formulated: Score={risk_score}/100 (Critical: {critical_count}, High: {high_count})",
                "success",
            )

            # Write findings and reports to database
            try:
                db.query(Finding).filter(Finding.scan_id == scan_id).delete()

                for f in final_security:
                    finding_obj = Finding(
                        scan_id=scan_id,
                        title=f.get("title", "Logical Vulnerability"),
                        description=f.get("description", "Semantic vulnerability flagged during hybrid AI audit."),
                        severity=f.get("severity", "Medium"),
                        file_path=f.get("file_path"),
                        line_number=f.get("line_number"),
                        code_snippet=f.get("code_snippet"),
                        cwe=f.get("cwe"),
                        cve=f.get("cve"),
                        mitre_attack=f.get("mitre_attack"),
                        owasp_category=f.get("owasp_category"),
                        confidence=f.get("confidence", "High"),
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
                    scan.risk_score = risk_score
                    scan.critical_count = critical_count
                    scan.high_count = high_count
                    scan.medium_count = medium_count
                    scan.low_count = low_count
                    scan.completed_at = datetime.datetime.now(datetime.timezone.utc)
                    scan.current_phase = "done"
                    scan.progress = 100
                    scan.report_raw = merged_report

                db.commit()
            except Exception as db_err:
                db.rollback()
                logger.exception("DB error storing findings in callback | scan_id=%s", scan_id)
                raise db_err

            elapsed = round(time.time() - start_time, 2)
            push_activity_log(
                "Orchestrator AI",
                f"Pipeline successfully completed in {elapsed}s. Export models are compiled and ready.",
                "success",
            )
            _broadcast(scan_id, "completed", {
                "scan_id": scan_id,
                "risk_score": risk_score,
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
            })

    except Exception as err:
        logger.exception("Callback aggregation execution failed | scan_id=%s", scan_id)
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
                    message=f"Pipeline aggregation failed: {str(err)}",
                    type="error",
                )
                db.add(activity)
                db.commit()
        except Exception as e:
            logger.exception("Failed to mark scan as failed in DB callback | scan_id=%s", scan_id)

        _broadcast(scan_id, "failed", {"scan_id": scan_id, "error": str(err)})
        raise self.retry(exc=err)

    finally:
        # Perform cleanup in finally block
        if temp_workspace_path:
            try:
                shutil.rmtree(temp_workspace_path, ignore_errors=True)
                logger.info("Cleaned up temporary git workspace path: %s", temp_workspace_path)
            except Exception as e:
                logger.exception("Failed to clean up temp workspace path: %s", temp_workspace_path)
        elif target_path:
            _cleanup_workspace(target_path)
