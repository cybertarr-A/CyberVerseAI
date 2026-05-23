import json
import logging
import time
from typing import Any, Optional
from groq import Groq, RateLimitError, APIConnectionError, APITimeoutError

from app.core.config import settings

logger = logging.getLogger("cyberverse.llm_client")


class LLMClient:
    """Thread-safe lazy singleton wrapper for Groq Cloud completions API client."""

    _instance: Optional["LLMClient"] = None

    @classmethod
    def get_instance(cls) -> "LLMClient":
        """Returns the lazy initialized LLMClient instance."""
        if cls._instance is None:
            cls._instance = LLMClient()
        return cls._instance

    def __init__(self):
        # Enforce strict key validation at initialization
        if not settings.GROQ_API_KEY or settings.GROQ_API_KEY.strip() in ("", "your_groq_api_key_here"):
            raise RuntimeError("GROQ_API_KEY missing")

        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL
        logger.info("Initialized CyberVerse LLM Gateway targeting Groq Cloud.")

    def generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Generates a text completion via Groq API using retry logic with backoff."""
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "LLM request attempt %d/%d targeting Groq (%s)...",
                    attempt,
                    max_attempts,
                    self.model
                )
                
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=self.model,
                    temperature=0.1,
                )
                
                content = chat_completion.choices[0].message.content
                logger.info("Groq API request successfully completed.")
                return content

            except RateLimitError as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "Rate limited by Groq API (429) on Attempt %d/%d. Retrying in %d seconds...",
                    attempt,
                    max_attempts,
                    wait_time
                )
                time.sleep(wait_time)
                
            except (APIConnectionError, APITimeoutError) as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "Groq API connection timeout or network error on Attempt %d/%d (Error: %s). Retrying in %d seconds...",
                    attempt,
                    max_attempts,
                    str(e),
                    wait_time
                )
                if attempt == max_attempts:
                    logger.error("Groq API connection failed after %d attempts.", max_attempts)
                    raise RuntimeError(
                        f"Groq API connection failed after {max_attempts} attempts due to time-out or network error: {e}"
                    ) from e
                time.sleep(wait_time)
                
            except Exception as e:
                logger.exception("Groq API execution encountered an unhandled exception: %s", e)
                raise RuntimeError(f"Groq API failed with an unhandled exception: {e}") from e
                
        raise RuntimeError(f"Groq API failed after {max_attempts} attempts.")

    def generate_structured_json(
        self, system_prompt: str, user_prompt: str, fallback_dict: Any
    ) -> Any:
        """Query LLM for structured JSON; raises exception on validation/API failures to enforce loud-failing."""
        json_system = (
            system_prompt
            + "\n\nCRITICAL: You MUST respond ONLY with a raw JSON block that exactly "
            "satisfies the required keys. Do not include introductory text or markdown."
        )

        response_text = self.generate_completion(json_system, user_prompt)
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
            return parsed
        except Exception as e:
            logger.exception(
                "Failed to parse LLM JSON response: %s",
                e,
            )
            raise ValueError(f"Unparseable JSON structure returned by Groq LLM: {e}") from e
