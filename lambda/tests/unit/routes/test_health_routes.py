"""Tests for the public health route."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.health import HealthRoute


def _client(**checks):
    app = FastAPI(title="test", version="9.9.9")
    HealthRoute(checks=checks).register(app.router)
    return TestClient(app)


class TestHealthRoute:
    def test_reports_healthy_dependencies(self):
        response = _client(dynamodb=lambda: None, s3=lambda: None).get("/v1/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["version"] == "9.9.9"
        assert body["timestamp"]
        assert body["dependencies"] == {
            "dynamodb": {"healthy": True},
            "s3": {"healthy": True},
        }

    def test_returns_503_when_a_dependency_fails(self):
        def boom():
            raise RuntimeError("dependency is down")

        response = _client(dynamodb=lambda: None, s3=boom).get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["dependencies"] == {
            "dynamodb": {"healthy": True},
            "s3": {"healthy": False},
        }

    def test_does_not_leak_the_dependency_error(self):
        def boom():
            raise RuntimeError("secret-looking detail")

        response = _client(s3=boom).get("/v1/health")

        assert "secret-looking detail" not in response.text
