"""
Redis pub/sub bridge between Celery workers and FastAPI WebSocket manager.
Workers publish scan events; the API process subscribes and broadcasts to clients.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCAN_EVENT_CHANNEL_PREFIX = "cyberverse:scan:"


def scan_channel(scan_id: str) -> str:
    return f"{SCAN_EVENT_CHANNEL_PREFIX}{scan_id}"


def publish_scan_event(redis_url: str, scan_id: str, payload: Dict[str, Any]) -> None:
    """Publish a scan event from a Celery worker (synchronous)."""
    try:
        import redis
        client = redis.from_url(redis_url, decode_responses=True, socket_timeout=5)
        message = json.dumps({"scan_id": scan_id, "payload": payload})
        client.publish(scan_channel(scan_id), message)
        client.close()
    except Exception as e:
        logger.exception(
            "Failed to publish scan event | scan_id=%s | event=%s | error=%s",
            scan_id,
            payload.get("event"),
            e,
        )


class ScanEventSubscriber:
    """Background asyncio task that listens for Redis scan events and forwards to WS."""

    def __init__(self, redis_url: str, ws_manager: Any):
        self.redis_url = redis_url
        self.ws_manager = ws_manager
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())
        logger.info("Scan event Redis subscriber started")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Scan event Redis subscriber stopped")

    async def _listen_loop(self) -> None:
        try:
            import redis.asyncio as aioredis
        except ImportError:
            logger.error("redis package missing async support; WS bridge disabled")
            return

        while self._running:
            pubsub = None
            client = None
            try:
                client = aioredis.from_url(self.redis_url, decode_responses=True)
                pubsub = client.pubsub()
                await pubsub.psubscribe(f"{SCAN_EVENT_CHANNEL_PREFIX}*")
                logger.info("Subscribed to Redis scan event channels")

                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] not in ("pmessage", "message"):
                        continue
                    try:
                        data = json.loads(message["data"])
                        scan_id = data.get("scan_id")
                        payload = data.get("payload", {})
                        if scan_id and payload:
                            await self.ws_manager.broadcast_event(scan_id, payload)
                    except Exception as e:
                        logger.exception("Failed to process Redis scan event: %s", e)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Redis subscriber connection error: %s", e)
                await asyncio.sleep(2)
            finally:
                if pubsub:
                    try:
                        await pubsub.aclose()
                    except Exception as e:
                        logger.exception("Failed to close Redis pubsub: %s", e)
                if client:
                    try:
                        await client.aclose()
                    except Exception as e:
                        logger.exception("Failed to close Redis client: %s", e)
