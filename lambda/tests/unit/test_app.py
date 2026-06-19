"""Tests for FastAPI app configuration."""

from fastapi.testclient import TestClient

from src.environment.service_provider import ServiceProvider
from src.shared.exceptions import BadRequestError, NotFoundError, UnauthorizedError


class TestCreateApp:
    def test_creates_fastapi_app(self, mock_service_provider):
        assert mock_service_provider.app is not None

    def test_health_endpoint(self, mock_service_provider):
        client = TestClient(mock_service_provider.app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestExceptionHandlers:
    def test_bad_request_returns_400(self):
        app = ServiceProvider().app

        @app.get("/test-bad-request")
        def _():
            raise BadRequestError("test bad request")

        client = TestClient(app)
        response = client.get("/test-bad-request")
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "BAD_REQUEST"
        assert body["error"]["message"] == "test bad request"

    def test_not_found_returns_404(self):
        app = ServiceProvider().app

        @app.get("/test-not-found")
        def _():
            raise NotFoundError("test not found")

        client = TestClient(app)
        response = client.get("/test-not-found")
        assert response.status_code == 404
        body = response.json()
        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["message"] == "test not found"

    def test_unauthorized_returns_401(self):
        app = ServiceProvider().app

        @app.get("/test-unauthorized")
        def _():
            raise UnauthorizedError("test unauthorized")

        client = TestClient(app)
        response = client.get("/test-unauthorized")
        assert response.status_code == 401
        body = response.json()
        assert body["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert body["error"]["message"] == "test unauthorized"

    def test_unhandled_exception_returns_structured_500(self):
        from src.shared.auth import get_current_user

        app = ServiceProvider().app

        def boom():
            raise RuntimeError("super secret internal detail")

        app.dependency_overrides[get_current_user] = boom
        client = TestClient(app, raise_server_exceptions=False)
        try:
            response = client.get("/v1/collections?vault_id=v")
            assert response.status_code == 500
            body = response.json()
            assert body["error"]["code"] == "INTERNAL_ERROR"
            assert body["error"]["message"] == "Internal server error"
            assert "super secret" not in response.text
        finally:
            app.dependency_overrides.clear()


def test_auth_and_recovery_routes_are_removed(client):
    """The stubbed auth + recovery endpoints must no longer be registered."""
    assert client.post("/v1/auth/login", json={}).status_code == 404
    assert client.post("/v1/auth/refresh", json={}).status_code == 404
    assert client.post("/v1/auth/recover", json={}).status_code == 404
    assert client.post("/v1/recovery/codes", json={}).status_code == 404
    assert client.post("/v1/recovery/validate", json={}).status_code == 404
