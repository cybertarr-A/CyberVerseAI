import json
import logging
import time
from typing import Any, Optional
import groq

from app.core.config import settings

logger = logging.getLogger("cyberverse.llm_client")


class LLMClient:
    def __init__(self):
        self._client: Optional[groq.Groq] = None
        logger.info("Initialized CyberVerse LLM Gateway targeting Groq Cloud.")

    @property
    def groq_key(self) -> Optional[str]:
        key = settings.GROQ_API_KEY
        if key:
            sanitized = key.strip().strip('"').strip("'")
            if sanitized and sanitized not in ("your-groq-api-key-here", ""):
                return sanitized
        return None

    @property
    def groq_model(self) -> str:
        return settings.GROQ_MODEL or "llama-3.3-70b-versatile"

    @property
    def client(self) -> groq.Groq:
        """Returns a cached, persistent Groq client instance."""
        if self._client is None:
            key = self.groq_key
            if not key:
                logger.warning("Groq API Key is missing. Operating without active LLM connection.")
                # We initialize with a dummy key so it doesn't crash on boot
                self._client = groq.Groq(api_key="dummy-key-for-local-boot")
            else:
                self._client = groq.Groq(api_key=key)
        return self._client

    def generate_completion(self, system_prompt: str, user_prompt: str, max_retries: int = 5) -> Optional[str]:
        """Generates a text completion via Groq API using retry logic with backoff."""
        key = self.groq_key
        model = self.groq_model
        if not key:
            logger.warning("Groq API Key is absent. Utilizing deterministic local heuristics.")
            return None

        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "LLM request attempt %d/%d targeting Groq (%s)...",
                    attempt,
                    max_attempts,
                    model
                )
                
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model=model,
                    temperature=0.1,
                )
                
                content = chat_completion.choices[0].message.content
                logger.info("Groq API request successfully completed.")
                return content

            except groq.RateLimitError as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "Rate limited by Groq API (429) on Attempt %d/%d. Retrying in %d seconds...",
                    attempt,
                    max_attempts,
                    wait_time
                )
                time.sleep(wait_time)
                
            except (groq.APIConnectionError, groq.APITimeoutError) as e:
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
        """Query LLM for structured JSON; fall back to template on failure."""
        json_system = (
            system_prompt
            + "\n\nCRITICAL: You MUST respond ONLY with a raw JSON block that exactly "
            "satisfies the required keys. Do not include introductory text or markdown."
        )

        response_text = self.generate_completion(json_system, user_prompt)
        if not response_text:
            return fallback_dict

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
            return fallback_dict


llm_client = LLMClient()
