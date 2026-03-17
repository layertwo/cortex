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
        assert response.json() == {"message": "test bad request"}

    def test_not_found_returns_404(self):
        app = ServiceProvider().app

        @app.get("/test-not-found")
        def _():
            raise NotFoundError("test not found")

        client = TestClient(app)
        response = client.get("/test-not-found")
        assert response.status_code == 404
        assert response.json() == {"message": "test not found"}

    def test_unauthorized_returns_401(self):
        app = ServiceProvider().app

        @app.get("/test-unauthorized")
        def _():
            raise UnauthorizedError("test unauthorized")

        client = TestClient(app)
        response = client.get("/test-unauthorized")
        assert response.status_code == 401
        assert response.json() == {"message": "test unauthorized"}
