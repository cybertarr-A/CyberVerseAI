import os
import shutil
import time
import datetime
import logging
import subprocess
import tempfile
from pathlib import Path
from celery import group
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
            update_scan_status("parsing", 20)
            push_activity_log(
                "Orchestrator AI",
                "Initiating codebase recursive chunking and formatting filters...",
                "info",
            )

            start_time = time.time()
            chunks = RepositoryChunker.chunk_repository(target_path)
            logger.info("Chunk count: %d", len(chunks))
            push_activity_log(
                "Orchestrator AI",
                f"Completed codebase chunking. Generated {len(chunks)} chunks for parallel analysis.",
                "info",
            )

            all_security = []
            all_architecture = []
            all_quality = []
            all_performance = []
            all_recommendations = []
            failed_chunks = 0
            results = []

            if chunks:
                update_scan_status("analyzing", 45)
                push_activity_log(
                    "Orchestrator AI",
                    f"Spawning {len(chunks)} Celery chunk analysis tasks in controlled batches (Max 3 concurrent)...",
                    "info",
                )

                # Split chunks into sublists of size 3
                batch_size = 3
                batches = [chunks[i:i + batch_size] for i in range(0, len(chunks), batch_size)]
                
                results = []
                processed_count = 0

                for batch_idx, batch in enumerate(batches, 1):
                    logger.info("Queue batch %d/%d with %d chunks...", batch_idx, len(batches), len(batch))
                    push_activity_log(
                        "Orchestrator AI",
                        f"Queueing controlled chunk batch {batch_idx}/{len(batches)}...",
                        "info"
                    )
                    
                    # Spawn batch using Celery group()
                    job = group(analyze_chunk.s(chunk) for chunk in batch)
                    async_result = job.apply_async(queue=settings.CELERY_QUEUE_NAME)
                    
                    # Wait/collect results for this batch
                    batch_results = async_result.join()
                    results.extend(batch_results)
                    
                    processed_count += len(batch)
                    logger.info("Batch %d/%d execution complete. Progress: %d/%d chunks.", batch_idx, len(batches), processed_count, len(chunks))

                logger.info("Controlled batch analysis tasks completed. Processing outcomes...")

                # Parse chunk processing progress
                for idx, r in enumerate(results, 1):
                    logger.info("Chunk processing progress: chunk %d/%d analyzed.", idx, len(chunks))
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
            else:
                push_activity_log(
                    "Orchestrator AI",
                    "No supported target code files found in the repository. Bypassing parallel tasks.",
                    "warning",
                )

            # 3. Merge results
            update_scan_status("enriching", 75)
            push_activity_log(
                "Orchestrator AI",
                "Consolidating parallel chunk results and generating dynamic Markdown threat report...",
                "info",
            )
            
            merged_report = ResultMerger.merge_results(results if chunks else [], failed_chunks, len(chunks))
            logger.info("Merge complete.")

            # Calculate risk statistics dynamically
            critical_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "critical")
            high_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "high")
            medium_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "medium")
            low_count = sum(1 for f in all_security if str(f.get("severity")).lower() == "low")
            
            # Deterministic risk scoring: Max 100
            base_score = float(critical_count * 25 + high_count * 15 + medium_count * 8 + low_count * 3)
            risk_score = min(100.0, base_score)

            update_scan_status("scoring", 90)
            push_activity_log(
                "Orchestrator AI",
                f"Scan risk profile formulated: Score={risk_score}/100 (Critical: {critical_count}, High: {high_count})",
                "success",
            )

            # 4. DB Storage
            try:
                db.query(Finding).filter(Finding.scan_id == scan_id).delete()

                for f in all_security:
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

                db.commit()
            except Exception as e:
                db.rollback()
                logger.exception(
                    "DB error storing findings | scan_id=%s | error=%s", scan_id, e
                )
                raise

            elapsed = time.time() - start_time
            logger.info("Task completion time: %.2f seconds.", elapsed)

            push_activity_log(
                "Orchestrator AI",
                f"Pipeline successfully completed in {elapsed:.1f}s. Export models are compiled and ready.",
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
