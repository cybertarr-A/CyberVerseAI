"""Tests for Redis sliding-window rate limiter behavior."""
import asyncio
import pytest
from app.core.rate_limiter import RedisSlidingWindowRateLimiter


def test_redis_limiter_rejects_invalid_rate():
    with pytest.raises(ValueError, match="rate"):
        RedisSlidingWindowRateLimiter(
            redis_url="redis://127.0.0.1:59999/0",
            rate=0,
            window_seconds=60,
        )


def test_redis_limiter_rejects_invalid_window():
    with pytest.raises(ValueError, match="window_seconds"):
        RedisSlidingWindowRateLimiter(
            redis_url="redis://127.0.0.1:59999/0",
            rate=10,
            window_seconds=0,
        )


def test_redis_limiter_hashes_client_identifier():
    limiter = RedisSlidingWindowRateLimiter(
        redis_url="redis://127.0.0.1:59999/0",
        rate=10,
        window_seconds=60,
    )
    key = limiter._client_key("192.168.1.1")
    assert key.startswith("cyberverse:ratelimit:")
    # IP should be hashed, not embedded verbatim
    assert "192.168.1.1" not in key


def test_redis_limiter_fails_open_without_redis_in_development_mode():
    """When redis_required=False (dev mode), allow requests even if Redis is unreachable."""
    limiter = RedisSlidingWindowRateLimiter(
        redis_url="redis://127.0.0.1:59999/0",
        rate=10,
        window_seconds=60,
        redis_required=False,
    )
    result = asyncio.run(limiter.allow_request("192.168.1.1"))
    assert result is True


def test_redis_limiter_fails_closed_when_required():
    """When redis_required=True (production), deny requests if Redis is unreachable."""
    limiter = RedisSlidingWindowRateLimiter(
        redis_url="redis://127.0.0.1:59999/0",
        rate=10,
        window_seconds=60,
        redis_required=True,
    )
    result = asyncio.run(limiter.allow_request("192.168.1.2"))
    assert result is False


def test_redis_limiter_custom_key_prefix():
    """Verify custom prefix is respected in generated keys."""
    limiter = RedisSlidingWindowRateLimiter(
        redis_url="redis://127.0.0.1:59999/0",
        rate=10,
        window_seconds=60,
        key_prefix="custom:rl",
    )
    key = limiter._client_key("10.0.0.1")
    assert key.startswith("custom:rl:")
