"""
Tests for the API entrypoint and app configuration.
"""

from fastapi.testclient import TestClient


class TestAppConfiguration:
    def test_health_endpoint(self, mock_service_provider):
        client = TestClient(mock_service_provider.app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_app_has_routes_registered(self, app):
        # FastAPI 0.138 stopped flattening included routers into app.routes
        # (each include is now a lazy _IncludedRouter). Use the OpenAPI schema,
        # the public contract for registered paths.
        paths = app.openapi()["paths"]
        assert "/v1/items" in paths
        assert "/v1/vaults" in paths

    def test_creates_fastapi_app(self, mock_service_provider):
        assert mock_service_provider.app is not None
        assert mock_service_provider.app.title == "Cortex API"
