"""
Redis-backed distributed sliding-window rate limiter.

The limiter uses an atomic Lua script so multiple API workers enforce the same
window without race conditions. Redis keys expire automatically, and a cleanup
method is available for operators that want active pruning.
"""
import asyncio
import hashlib
import logging
import time
import uuid
from typing import Optional

logger = logging.getLogger(__name__)


_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local expires = tonumber(ARGV[5])

redis.call("ZREMRANGEBYSCORE", key, 0, now_ms - window_ms)
local current = redis.call("ZCARD", key)

if current >= limit then
    redis.call("EXPIRE", key, expires)
    return {0, current}
end

redis.call("ZADD", key, now_ms, member)
redis.call("EXPIRE", key, expires)
return {1, current + 1}
"""


class RedisSlidingWindowRateLimiter:
    """
    Distributed sliding-window rate limiter using Redis sorted sets.

    In production, set RATE_LIMIT_REDIS_REQUIRED=true so Redis failures deny
    requests instead of silently weakening throttling. Development defaults can
    fail open so local test runs do not require Redis.
    """

    def __init__(
        self,
        redis_url: str,
        rate: int = 10,
        window_seconds: int = 60,
        key_prefix: str = "cyberverse:ratelimit",
        redis_required: bool = False,
    ):
        if rate < 1:
            raise ValueError("rate must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")

        self.rate = rate
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix
        self.redis_required = redis_required
        self._redis = None
        self._script = None
        self._redis_url = redis_url

    def _get_redis(self):
        if self._redis is None:
            import redis

            self._redis = redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._redis

    def _client_key(self, client_id: str) -> str:
        digest = hashlib.sha256(client_id.encode("utf-8")).hexdigest()
        return f"{self.key_prefix}:{digest}"

    async def allow_request(self, client_id: str) -> bool:
        try:
            return await asyncio.to_thread(self._check_sliding_window, client_id)
        except Exception as exc:
            logger.exception("Redis rate limiter unavailable: %s", exc)
            return not self.redis_required

    def _check_sliding_window(self, client_id: str) -> bool:
        redis_client = self._get_redis()
        if self._script is None:
            self._script = redis_client.register_script(_SLIDING_WINDOW_LUA)

        now_ms = int(time.time() * 1000)
        window_ms = self.window_seconds * 1000
        member = f"{now_ms}:{uuid.uuid4()}"
        result = self._script(
            keys=[self._client_key(client_id)],
            args=[now_ms, window_ms, self.rate, member, self.window_seconds + 30],
        )
        return bool(result[0])

    async def cleanup_stale_buckets(self, max_age_seconds: Optional[int] = None) -> int:
        """Prune expired entries and remove empty rate-limit keys."""
        try:
            return await asyncio.to_thread(self._cleanup_stale_buckets, max_age_seconds)
        except Exception as exc:
            logger.exception("Redis rate limiter cleanup failed: %s", exc)
            return 0

    def _cleanup_stale_buckets(self, max_age_seconds: Optional[int]) -> int:
        redis_client = self._get_redis()
        cutoff_ms = int((time.time() - (max_age_seconds or self.window_seconds)) * 1000)
        removed_keys = 0
        for key in redis_client.scan_iter(f"{self.key_prefix}:*"):
            redis_client.zremrangebyscore(key, 0, cutoff_ms)
            if redis_client.zcard(key) == 0:
                redis_client.delete(key)
                removed_keys += 1
        return removed_keys


def create_rate_limiter(
    redis_url: str,
    rate: int = 10,
    window_seconds: int = 60,
    redis_required: bool = False,
):
    return RedisSlidingWindowRateLimiter(
        redis_url=redis_url,
        rate=rate,
        window_seconds=window_seconds,
        redis_required=redis_required,
    )
