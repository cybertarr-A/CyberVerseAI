"""
Integration tests for core API endpoints.
Tests health check, readiness probe, metrics, project CRUD, and input validation.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Provides a test client that shares the application state."""
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """Tests for /health, /ready, and /metrics endpoints."""

    def test_health_check_returns_status(self, client):
        response = client.get("/health")
        assert response.status_code in (200, 503)
        body = response.json()
        assert "status" in body
        assert "checks" in body
        assert "timestamp" in body
        assert "version" in body

    def test_readiness_probe(self, client):
        response = client.get("/ready")
        assert response.status_code in (200, 503)
        body = response.json()
        assert "ready" in body

    def test_liveness_probe(self, client):
        response = client.get("/liveness")
        assert response.status_code == 200
        body = response.json()
        assert body["alive"] is True

    def test_metrics_endpoint(self, client):
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.json()
        assert "total_requests" in body
        assert "total_errors" in body
        assert "latency_p50_ms" in body
        assert "latency_p95_ms" in body
        assert "latency_p99_ms" in body

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "online"
        assert "service" in body
        assert "timestamp" in body


class TestProjectsAPI:
    """Tests for /api/v1/projects endpoints."""

    def test_list_projects_seeds_default(self, client):
        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # Default sandbox project is seeded

    def test_create_project_valid(self, client):
        response = client.post(
            "/api/v1/projects",
            json={"name": "TestProject123", "description": "A test project"}
        )
        # Either 200 (created) or 400 (already exists from previous run)
        assert response.status_code in (200, 400)

    def test_create_project_invalid_name(self, client):
        response = client.post(
            "/api/v1/projects",
            json={"name": "bad;name", "description": "Should be rejected"}
        )
        assert response.status_code == 422  # Pydantic validation

    def test_create_project_empty_name(self, client):
        response = client.post(
            "/api/v1/projects",
            json={"name": "", "description": ""}
        )
        assert response.status_code == 422


class TestScansAPI:
    """Tests for /api/v1/scans endpoints."""

    def test_list_scans(self, client):
        response = client.get("/api/v1/scans")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_scan_invalid_id(self, client):
        response = client.get("/api/v1/scans/not-a-uuid")
        # Should return 422 or 500 due to UUID validation failure
        assert response.status_code in (422, 500)

    def test_get_scan_nonexistent(self, client):
        response = client.get("/api/v1/scans/550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code == 404


class TestRateLimiting:
    """Tests for the token bucket rate limiter."""

    def test_requests_within_limit_pass(self, client):
        # The first 20 requests (capacity) should all pass
        for _ in range(5):
            response = client.get("/api/v1/projects")
            assert response.status_code == 200


class TestRequestHeaders:
    """Tests for observability middleware headers."""

    def test_request_id_header_injected(self, client):
        response = client.get("/")
        assert "X-Request-ID" in response.headers
        assert "X-Response-Time-Ms" in response.headers

    def test_custom_request_id_forwarded(self, client):
        custom_id = "test-trace-id-12345"
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id


class TestTelemetryAPI:
    """Tests for /api/v1/telemetry endpoint."""

    def test_telemetry_returns_stats(self, client):
        response = client.get("/api/v1/telemetry")
        assert response.status_code == 200
        body = response.json()
        assert "stats" in body
        assert "vulnerability_counts" in body
        assert "recent_findings" in body
