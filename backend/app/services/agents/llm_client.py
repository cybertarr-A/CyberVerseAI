import json
import logging
import time
import random
import redis
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
        
        # Initialize Redis client for locking and rate limiting
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        logger.info("Initialized CyberVerse LLM Gateway targeting Groq Cloud.")

    def generate_completion(self, system_prompt: str, user_prompt: str) -> str:
        """Generates a text completion via Groq API using retry logic with backoff."""
        max_attempts = 5
        logger.info("[LOG] Request started")
        
        # Redis-based distributed locking & throttling keys
        lock_key = "cyberverse:lock:groq_request"
        cooldown_key = "cyberverse:groq_cooldown"
        
        # Configure limits (can fall back if not explicitly in settings)
        max_concurrent = getattr(settings, "GROQ_MAX_CONCURRENT_REQUESTS", 1)
        cooldown_period = getattr(settings, "GROQ_COOLDOWN_PERIOD", 2.0)
        
        # We will attempt to acquire the lock. 
        # If another task has it, we are "throttled" and wait/retry.
        # We use a simple auto-expiring Redis lock.
        lock = self.redis_client.lock(lock_key, timeout=60)
        
        acquired = False
        # Retry lock acquisition to implement safe queuing without flooding workers
        for lock_attempt in range(1, max_attempts + 1):
            try:
                acquired = lock.acquire(blocking=False)
                if acquired:
                    break
            except Exception as e:
                logger.error("Redis locking error encountered: %s. Falling back to safe execution.", e)
                # Fail-open/safe if Redis is completely down
                acquired = True
                break
            
            logger.warning("[LOG] Request throttled")
            lock_delay = min((2 ** lock_attempt) + random.uniform(1, 5), 30.0)
            logger.warning("[LOG] Retry delay: %.2f seconds", lock_delay)
            time.sleep(lock_delay)
            
        if not acquired:
            logger.error("Failed to acquire Redis distributed request lock after all attempts.")
            raise RuntimeError("Request throttled: Redis lock unavailable.")

        try:
            # We got the lock! Now let's enforce frequency throttling (cooldown)
            while True:
                try:
                    last_request_time = self.redis_client.get(cooldown_key)
                    if last_request_time:
                        elapsed = time.time() - float(last_request_time)
                        if elapsed < cooldown_period:
                            wait_time = cooldown_period - elapsed
                            logger.warning("[LOG] Request throttled")
                            time.sleep(wait_time)
                            continue
                except Exception as e:
                    logger.error("Redis cooldown check failed: %s. Proceeding.", e)
                break
            
            # Update the last request timestamp
            try:
                self.redis_client.set(cooldown_key, str(time.time()))
            except Exception as e:
                logger.error("Redis set cooldown failed: %s", e)
                
            logger.info("[LOG] Request resumed")
            
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
                    logger.info("[LOG] Task completed")
                    return content

                except RateLimitError as e:
                    logger.warning("[LOG] Rate limit detected")
                    retry_after = None
                    if hasattr(e, "response") and e.response is not None:
                        retry_after = e.response.headers.get("retry-after")
                    elif hasattr(e, "headers") and e.headers is not None:
                        retry_after = e.headers.get("retry-after")
                        
                    wait_time = min((2 ** attempt) + random.uniform(1, 5), 60.0)
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            pass
                            
                    logger.warning(
                        "[LOG] Retry delay: %.2f seconds",
                        wait_time
                    )
                    time.sleep(wait_time)
                    
                except (APIConnectionError, APITimeoutError) as e:
                    wait_time = min((2 ** attempt) + random.uniform(1, 5), 60.0)
                    logger.warning(
                        "Groq API connection timeout or network error on Attempt %d/%d (Error: %s). Retrying in %.2f seconds...",
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
        finally:
            # Always release the lock if it was acquired
            if acquired:
                try:
                    lock.release()
                except Exception as e:
                    logger.error("Failed to release Redis request lock: %s", e)

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
