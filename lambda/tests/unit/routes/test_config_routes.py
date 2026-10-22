"""Tests for the public runtime-configuration route."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.config import ConfigRoute


def _client(issuer: str = "https://idp.example.com", client_id: str = "cortex") -> TestClient:
    app = FastAPI()
    config = SimpleNamespace(oidc_issuer=issuer, oidc_client_id=client_id)
    ConfigRoute(config=config).register(app.router)
    return TestClient(app)


class TestConfigRoute:
    def test_returns_the_oidc_settings(self):
        response = _client().get("/v1/config")

        assert response.status_code == 200
        assert response.json() == {
            "oidcIssuer": "https://idp.example.com",
            "oidcClientId": "cortex",
        }

    def test_returns_503_when_not_configured(self):
        response = _client(issuer="", client_id="").get("/v1/config")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "NOT_CONFIGURED"
