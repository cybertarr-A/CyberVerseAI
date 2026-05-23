import json
import logging
import httpx
import time
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger("cyberverse.llm_client")


class LLMClient:
    def __init__(self):
        limits = httpx.Limits(
            max_keepalive_connections=20,
            max_connections=50
        )
        timeout = httpx.Timeout(
            connect=30.0,
            read=300.0,
            write=30.0,
            pool=30.0
        )
        self.client = httpx.Client(limits=limits, timeout=timeout)
        logger.info("Initialized CyberVerse LLM Gateway targeting Nvidia NIM with persistent client pooling.")

    @property
    def nvidia_key(self) -> Optional[str]:
        key = settings.NVIDIA_API_KEY
        if key:
            sanitized = key.strip().strip('"').strip("'")
            if sanitized and sanitized not in ("your-nvidia-api-key-here", ""):
                return sanitized
        return None

    @property
    def nvidia_model(self) -> str:
        return settings.NVIDIA_MODEL or "moonshotai/kimi-k2.6"

    def generate_completion(self, system_prompt: str, user_prompt: str, max_retries: int = 5) -> Optional[str]:
        """Generates a text completion via Nvidia NIM API using retry logic with backoff."""
        key = self.nvidia_key
        model = self.nvidia_model
        if not key:
            logger.warning("Nvidia API Key is absent. Utilizing deterministic local heuristics.")
            return None

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
        }
        
        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(
                    "Dispatching prompt to Nvidia NIM (%s) [Attempt %d/%d]...",
                    model,
                    attempt,
                    max_attempts
                )
                response = self.client.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(
                        "Rate limited by Nvidia NIM (429). Attempt %d/%d. Retrying in %d seconds...",
                        attempt,
                        max_attempts,
                        wait_time
                    )
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.NetworkError) as e:
                wait_time = 2 ** attempt
                logger.warning(
                    "Nvidia NIM API connection/timeout error on Attempt %d/%d (Error: %s). Retrying in %d seconds...",
                    attempt,
                    max_attempts,
                    str(e),
                    wait_time
                )
                if attempt == max_attempts:
                    logger.error("Nvidia NIM LLM connection failed after %d attempts.", max_attempts)
                    raise RuntimeError(
                        f"Nvidia NIM LLM API connection failed after {max_attempts} attempts due to time-out or network error: {e}"
                    ) from e
                time.sleep(wait_time)
            except Exception as e:
                logger.exception("Nvidia NIM API execution encountered an unhandled exception: %s", e)
                raise RuntimeError(f"Nvidia NIM API failed with an unhandled exception: {e}") from e
                
        raise RuntimeError(f"Nvidia NIM API failed after {max_attempts} attempts.")

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
