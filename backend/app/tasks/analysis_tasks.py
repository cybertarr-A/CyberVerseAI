import logging
import time
from typing import Dict, Any

from app.core.celery import celery_app
from app.services.agents.llm_client import LLMClient

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
    """
    Parallel Celery task that queries the Groq LLM to analyze a single
    code chunk for security vulnerabilities, architecture, quality, performance, and recommendations.
    """
    task_id = self.request.id or "local-task"
    logger.info("START: Celery analysis task %s initialized.", task_id)
    
    start_time = time.monotonic()

    system_prompt = """You are an elite application architect and production reliability engineer.
Your task is to analyze the provided code chunk.

Identify issues across exactly these five categories:
1. Security findings: vulnerabilities, logical security flaws, credentials (keys/tokens) exposures.
2. Architecture issues: anti-patterns, structural design flaws, tight coupling, separation of concerns.
3. Code quality: technical debt, readability, standard conventions, lack of comments, complex structures.
4. Performance concerns: memory leak vectors, database query inefficiencies, slow CPU loops, caching opportunities.
5. Recommendations: concise suggestions to optimize or fix identified issues.

Respond ONLY with a JSON object that satisfies this exact schema:
{
  "security_findings": [
    {
      "title": "Finding Title",
      "description": "Clear explanation of the security issue",
      "severity": "Critical|High|Medium|Low",
      "file_path": "Filename or path",
      "line_number": 12
    }
  ],
  "architecture_issues": [
    {
      "title": "Issue Title",
      "description": "Architectural critique",
      "severity": "High|Medium|Low"
    }
  ],
  "code_quality": [
    {
      "title": "Debt Title",
      "description": "Readability or quality issue description",
      "severity": "High|Medium|Low"
    }
  ],
  "performance_concerns": [
    {
      "title": "Bottleneck Title",
      "description": "Performance concern details",
      "severity": "High|Medium|Low"
    }
  ],
  "recommendations": [
    "Opt-in recommendation statement 1",
    "Opt-in recommendation statement 2"
  ]
}

If a category has no issues, provide an empty list: [].
Do not wrap JSON in Markdown decorators, introductory text, or closing notes.
"""

    fallback_dict = {
        "security_findings": [],
        "architecture_issues": [],
        "code_quality": [],
        "performance_concerns": [],
        "recommendations": []
    }

    try:
        logger.info("PROCESSING: Dispatching codebase chunk for Groq LLM auditing on task %s.", task_id)
        
        result = LLMClient.get_instance().generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=chunk,
            fallback_dict=fallback_dict
        )
        
        logger.info("FINISHED: Received structured response for task %s.", task_id)
        
        duration = round(time.monotonic() - start_time, 2)
        logger.info("COMPLETE: Task %s completed successfully in %.2fs.", task_id, duration)
        
        return {
            "status": "success",
            "task_id": task_id,
            "duration": duration,
            "data": result
        }
        
    except Exception as exc:
        duration = round(time.monotonic() - start_time, 2)
        failure_reason = str(exc)
        
        logger.error(
            "COMPLETE: Task %s failed after %.2fs. Reason: %s. Returning graceful fallback.",
            task_id,
            duration,
            failure_reason,
            exc_info=True
        )
        
        # Graceful fallback returning partial success
        return {
            "status": "partial_success",
            "error": "rate_limit",
            "data": fallback_dict
        }