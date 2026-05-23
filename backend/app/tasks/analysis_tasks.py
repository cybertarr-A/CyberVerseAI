import logging
from typing import Dict, Any

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
    """
    Parallel Celery task that queries the Nvidia NIM LLM to analyze a single
    code chunk for security vulnerabilities, architecture, quality, performance, and recommendations.
    """
    logger.info("Celery analysis task %s started on chunk.", self.request.id)

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
        result = llm_client.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=chunk,
            fallback_dict=fallback_dict
        )
        return {
            "status": "success",
            "data": result
        }
    except Exception as exc:
        logger.exception("Failed to analyze codebase chunk: %s", exc)
        return {
            "status": "failed",
            "error": str(exc)
        }
