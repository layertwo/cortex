"""
Tests for the API entrypoint and app configuration.
"""


class TestAppConfiguration:
    def test_health_routes_registered(self, mock_service_provider):
        paths = mock_service_provider.app.openapi()["paths"]
        assert "get" in paths["/v1/health"]
        assert "get" in paths["/health"]

    def test_app_has_routes_registered(self, app):
        # FastAPI 0.138 stopped flattening included routers into app.routes
        # (each include is now a lazy _IncludedRouter). Use the OpenAPI schema,
        # the public contract for registered paths.
        paths = app.openapi()["paths"]
        assert "/v1/items" in paths
        assert "/v1/vaults" in paths
        assert {"get", "post"} <= set(paths["/v1/vaults"])
        assert "/v1/vaults/{vault_id}" in paths
        assert {"get", "put", "delete"} <= set(paths["/v1/vaults/{vault_id}"])

    def test_creates_fastapi_app(self, mock_service_provider):
        assert mock_service_provider.app is not None
        assert mock_service_provider.app.title == "Cortex API"
