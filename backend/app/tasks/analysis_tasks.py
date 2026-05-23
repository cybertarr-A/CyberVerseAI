import logging
import time
from typing import Dict, Any

import httpx
from celery.exceptions import SoftTimeLimitExceeded

from app.core.celery import celery_app
from app.services.agents.llm_client import llm_client

logger = logging.getLogger("cyberverse.analysis_tasks")


@celery_app.task(
    name="app.tasks.analysis_tasks.analyze_chunk",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    time_limit=360,
    soft_time_limit=300
)
def analyze_chunk(self, chunk: str) -> Dict[str, Any]:

    task_id = self.request.id
    start_time = time.time()

    logger.info(
        f"[START] Chunk task={task_id}"
    )

    system_prompt = """
You are an elite application architect and production reliability engineer.

Analyze this code and produce ONLY valid JSON.

Categories:

1 Security findings
2 Architecture issues
3 Code quality
4 Performance concerns
5 Recommendations

Return only schema-compliant JSON.
"""

    fallback_dict = {
        "security_findings": [],
        "architecture_issues": [],
        "code_quality": [],
        "performance_concerns": [],
        "recommendations": []
    }

    try:

        logger.info(
            f"[PROCESSING] task={task_id}"
        )

        result = llm_client.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=chunk,
            fallback_dict=fallback_dict
        )

        execution_time = round(
            time.time()-start_time,
            2
        )

        logger.info(
            f"[FINISHED] task={task_id} duration={execution_time}s"
        )

        return {

            "status":"success",

            "task_id":task_id,

            "duration":execution_time,

            "data":result
        }

    except (
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.NetworkError
    ) as exc:

        logger.warning(
            f"[RETRY] task={task_id} reason={str(exc)}"
        )

        raise self.retry(
            exc=exc
        )

    except SoftTimeLimitExceeded:

        logger.exception(
            f"[TIME_LIMIT] task={task_id}"
        )

        return {

            "status":"timeout",

            "task_id":task_id,

            "error":"Task exceeded soft limit"
        }

    except Exception as exc:

        logger.exception(
            f"[FAILED] task={task_id}"
        )

        return {

            "status":"failed",

            "task_id":task_id,

            "error":str(exc)
        }

    finally:

        logger.info(
            f"[COMPLETE] task={task_id}"
        )