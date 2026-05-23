import logging
from typing import Dict, Any
from app.services.agents.llm_client import llm_client

logger = logging.getLogger("cyberverse.groq_health")


def test_groq() -> Dict[str, Any]:
    """
    Sends a small test request to Groq API to verify direct connectivity and API key validity.
    Returns {"status": "healthy"} on success, or {"status": "failed", "error": "..."} on error.
    """
    try:
        logger.info("Executing live Groq API health connectivity test...")
        # Send a highly efficient lightweight request
        response = llm_client.generate_completion(
            system_prompt="You are a health checker. Respond with exactly the word OK.",
            user_prompt="Respond with OK"
        )
        if response and "OK" in response.upper():
            logger.info("Groq API health check: SUCCESS. Connection is healthy.")
            return {"status": "healthy"}
        else:
            logger.warning("Groq API health check: UNEXPECTED RESPONSE: %s", response)
            return {
                "status": "failed",
                "error": f"Unexpected response from LLM: {response}"
            }
    except Exception as e:
        logger.error("Groq API health check: FAILED. Error: %s", e, exc_info=True)
        return {
            "status": "failed",
            "error": str(e)
        }
