"""Tests for authentication utilities."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.shared.auth import get_current_user
from src.shared.exceptions import UnauthorizedError


class TestGetCurrentUser:
    """Test the FastAPI auth dependency."""

    def _make_app(self):
        app = FastAPI()
        app.state.config = SimpleNamespace(
            oidc_issuer="https://idp.example.com", oidc_client_id="cortex"
        )

        @app.get("/test")
        def test_route(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}

        return app

    def test_extracts_user_from_cognito_claims(self):
        """Mangum forwards API Gateway context via scope['aws.event']."""
        from src.shared.auth import extract_user_id

        event = {"requestContext": {"authorizer": {"claims": {"sub": "user-123"}}}}
        assert extract_user_id(event) == "user-123"

    def test_extracts_user_from_principal_id(self):
        from src.shared.auth import extract_user_id

        event = {"requestContext": {"authorizer": {"principalId": "user-456"}}}
        assert extract_user_id(event) == "user-456"

    def test_prefers_claims_sub_over_principal_id(self):
        from src.shared.auth import extract_user_id

        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "user-from-claims"},
                    "principalId": "user-from-principal",
                }
            }
        }
        assert extract_user_id(event) == "user-from-claims"

    def test_raises_when_no_user_id(self):
        from src.shared.auth import extract_user_id

        event: dict[str, Any] = {"requestContext": {"authorizer": {}}}
        with pytest.raises(UnauthorizedError, match="User identity not found"):
            extract_user_id(event)

    def test_raises_when_no_authorizer(self):
        from src.shared.auth import extract_user_id

        event: dict[str, Any] = {"requestContext": {}}
        with pytest.raises(UnauthorizedError, match="User identity not found"):
            extract_user_id(event)

    def test_raises_when_no_request_context(self):
        from src.shared.auth import extract_user_id

        event: dict[str, Any] = {}
        with pytest.raises(UnauthorizedError, match="User identity not found"):
            extract_user_id(event)

    def test_validates_the_bearer_token_outside_api_gateway(self, monkeypatch):
        from src.shared import auth

        seen = {}
        monkeypatch.setattr(
            auth,
            "verify_token",
            lambda token, issuer, client_id: (
                seen.update(issuer=issuer, client_id=client_id, token=token) or "user-789"
            ),
        )
        client = TestClient(self._make_app())

        response = client.get("/test", headers={"Authorization": "Bearer token-1"})

        assert response.status_code == 200
        assert response.json() == {"user_id": "user-789"}
        assert seen == {
            "issuer": "https://idp.example.com",
            "client_id": "cortex",
            "token": "token-1",
        }

    def test_requires_a_bearer_token_outside_api_gateway(self):
        from starlette.requests import Request

        with pytest.raises(UnauthorizedError, match="Authentication required"):
            get_current_user(Request({"type": "http", "headers": []}))

    def test_ignores_non_bearer_authorization(self):
        from starlette.requests import Request

        request = Request({"type": "http", "headers": [(b"authorization", b"Basic abc")]})
        with pytest.raises(UnauthorizedError, match="Authentication required"):
            get_current_user(request)
