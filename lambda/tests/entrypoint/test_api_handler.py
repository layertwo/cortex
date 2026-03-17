"""
Tests for the API entrypoint and app configuration.
"""

from fastapi.testclient import TestClient

from src.environment.service_provider import ServiceProvider


class TestAppConfiguration:
    def test_health_endpoint(self, mock_service_provider):
        client = TestClient(mock_service_provider.app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_app_has_routes_registered(self, app):
        routes = [r.path for r in app.routes]
        assert "/v1/auth/login" in routes
        assert "/v1/items" in routes
        assert "/v1/vaults" in routes

    def test_creates_fastapi_app(self, mock_service_provider):
        assert mock_service_provider.app is not None
        assert mock_service_provider.app.title == "Cortex API"
