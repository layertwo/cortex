"""Tests for the public runtime-configuration route."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.config import ConfigRoute


def _client() -> TestClient:
    app = FastAPI()
    ConfigRoute().register(app.router)
    return TestClient(app)


class TestConfigRoute:
    def test_returns_the_oidc_settings(self, monkeypatch):
        monkeypatch.setenv("OIDC_ISSUER", "https://idp.example.com/")
        monkeypatch.setenv("OIDC_CLIENT_ID", "cortex")

        response = _client().get("/v1/config")

        assert response.status_code == 200
        assert response.json() == {
            "oidcIssuer": "https://idp.example.com",
            "oidcClientId": "cortex",
        }

    def test_returns_503_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("OIDC_ISSUER", raising=False)
        monkeypatch.delenv("OIDC_CLIENT_ID", raising=False)

        response = _client().get("/v1/config")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "NOT_CONFIGURED"
