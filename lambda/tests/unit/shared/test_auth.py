"""Tests for authentication utilities."""

import pytest
from fastapi import FastAPI

from src.shared.auth import get_current_user
from src.shared.exceptions import UnauthorizedError


class TestGetCurrentUser:
    """Test the FastAPI auth dependency."""

    def _make_app(self):
        app = FastAPI()

        @app.get("/test")
        def test_route(user_id: str = get_current_user):
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

        event = {"requestContext": {"authorizer": {}}}
        with pytest.raises(UnauthorizedError, match="User identity not found"):
            extract_user_id(event)

    def test_raises_when_no_authorizer(self):
        from src.shared.auth import extract_user_id

        event = {"requestContext": {}}
        with pytest.raises(UnauthorizedError, match="User identity not found"):
            extract_user_id(event)

    def test_raises_when_no_request_context(self):
        from src.shared.auth import extract_user_id

        event = {}
        with pytest.raises(UnauthorizedError, match="User identity not found"):
            extract_user_id(event)
