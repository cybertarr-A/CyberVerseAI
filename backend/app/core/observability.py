"""
Production observability: structured logging helpers, Prometheus metrics,
OpenTelemetry tracing, and system resource monitoring.
"""
import asyncio
import logging
import time
from contextlib import contextmanager
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics (prometheus_client)
# ---------------------------------------------------------------------------
try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    HTTP_REQUESTS_TOTAL = Counter(
        "cyberverse_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )
    HTTP_REQUEST_DURATION = Histogram(
        "cyberverse_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )
    ACTIVE_SCANS = Gauge("cyberverse_active_scans", "Currently running scans")
    WEBSOCKET_CONNECTIONS = Gauge(
        "cyberverse_websocket_connections", "Active WebSocket connections"
    )
    AGENT_EXECUTION_DURATION = Histogram(
        "cyberverse_agent_execution_seconds",
        "Agent pipeline stage duration",
        ["agent"],
        buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    )
    CELERY_QUEUE_LENGTH = Gauge(
        "cyberverse_celery_queue_length", "Pending Celery tasks in queue"
    )
    MEMORY_USAGE_BYTES = Gauge(
        "cyberverse_memory_usage_bytes", "Process memory usage in bytes"
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client not installed; /metrics/prometheus disabled")


def prometheus_metrics() -> tuple:
    """Return (content, content_type) for Prometheus scrape endpoint."""
    if not PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n", "text/plain"
    return generate_latest(), CONTENT_TYPE_LATEST


# ---------------------------------------------------------------------------
# OpenTelemetry tracing
# ---------------------------------------------------------------------------
_tracer = None


def setup_tracing(service_name: str = "cyberverse-api") -> None:
    """Initialize OpenTelemetry tracing if dependencies are available."""
    global _tracer
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        logger.info("OpenTelemetry tracing initialized for %s", service_name)
    except ImportError:
        logger.info("OpenTelemetry not installed; tracing disabled")


def get_tracer():
    return _tracer


# ---------------------------------------------------------------------------
# In-process metrics collector (JSON snapshot for /metrics)
# ---------------------------------------------------------------------------
class MetricsCollector:
    """In-process request metrics for JSON /metrics endpoint."""

    def __init__(self):
        self.request_count: int = 0
        self.error_count: int = 0
        self.scan_count: int = 0
        self.active_scans: int = 0
        self._endpoint_counts: Dict[str, int] = {}
        self._latencies: list = []
        self._lock = asyncio.Lock()

    async def record_request(
        self, method: str, path: str, status_code: int, latency_ms: float
    ):
        async with self._lock:
            self.request_count += 1
            if status_code >= 400:
                self.error_count += 1
            key = f"{method} {path}"
            self._endpoint_counts[key] = self._endpoint_counts.get(key, 0) + 1
            self._latencies.append(latency_ms)
            if len(self._latencies) > 1000:
                self._latencies = self._latencies[-1000:]

        if PROMETHEUS_AVAILABLE:
            HTTP_REQUESTS_TOTAL.labels(
                method=method, endpoint=path, status=str(status_code)
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=method, endpoint=path).observe(
                latency_ms / 1000.0
            )

    async def snapshot(self) -> dict:
        async with self._lock:
            sorted_latencies = sorted(self._latencies) if self._latencies else [0]
            p50_idx = max(0, int(len(sorted_latencies) * 0.50) - 1)
            p95_idx = max(0, int(len(sorted_latencies) * 0.95) - 1)
            p99_idx = max(0, int(len(sorted_latencies) * 0.99) - 1)
            return {
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "total_scans_dispatched": self.scan_count,
                "active_scans": self.active_scans,
                "latency_p50_ms": round(sorted_latencies[p50_idx], 2),
                "latency_p95_ms": round(sorted_latencies[p95_idx], 2),
                "latency_p99_ms": round(sorted_latencies[p99_idx], 2),
                "top_endpoints": dict(
                    sorted(self._endpoint_counts.items(), key=lambda x: -x[1])[:10]
                ),
            }


def update_system_metrics(ws_connections: int = 0, active_scans: int = 0) -> dict:
    """Collect memory and process metrics using psutil."""
    result = {"websocket_connections": ws_connections, "active_scans": active_scans}
    try:
        import psutil
        proc = psutil.Process()
        mem = proc.memory_info()
        result["memory_rss_mb"] = round(mem.rss / (1024 * 1024), 2)
        result["memory_vms_mb"] = round(mem.vms / (1024 * 1024), 2)
        result["cpu_percent"] = proc.cpu_percent(interval=0.1)
        if PROMETHEUS_AVAILABLE:
            MEMORY_USAGE_BYTES.set(mem.rss)
            WEBSOCKET_CONNECTIONS.set(ws_connections)
            ACTIVE_SCANS.set(active_scans)
    except ImportError:
        result["memory_rss_mb"] = None
    except Exception as e:
        logger.exception("Failed to collect system metrics: %s", e)
    return result


def update_queue_metrics(redis_url: str, queue_name: str = "celery") -> dict:
    """Collect Celery queue length from Redis without failing health checks."""
    result = {"queue": queue_name, "pending_tasks": None}
    try:
        import redis

        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        pending = int(client.llen(queue_name))
        client.close()
        result["pending_tasks"] = pending
        if PROMETHEUS_AVAILABLE:
            CELERY_QUEUE_LENGTH.set(pending)
    except Exception as exc:
        logger.exception("Failed to collect queue metrics: %s", exc)
    return result


def record_agent_execution(agent: str, duration_seconds: float) -> None:
    """Record agent stage execution duration in Prometheus when available."""
    if PROMETHEUS_AVAILABLE:
        AGENT_EXECUTION_DURATION.labels(agent=agent).observe(duration_seconds)


@contextmanager
def agent_timer(agent: str):
    started = time.monotonic()
    try:
        yield
    finally:
        record_agent_execution(agent, time.monotonic() - started)


def log_with_context(
    level: int,
    message: str,
    *,
    scan_id: Optional[str] = None,
    agent: Optional[str] = None,
    file_path: Optional[str] = None,
    request_id: Optional[str] = None,
):
    """Emit structured log with optional scan/agent/file/request context."""
    extra_parts = []
    if scan_id:
        extra_parts.append(f"scan_id={scan_id}")
    if agent:
        extra_parts.append(f"agent={agent}")
    if file_path:
        extra_parts.append(f"file={file_path}")
    if request_id:
        extra_parts.append(f"request_id={request_id}")
    ctx = " | ".join(extra_parts)
    full_msg = f"{message} | {ctx}" if ctx else message
    logger.log(level, full_msg)
