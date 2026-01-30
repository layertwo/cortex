"""
Unit tests for shared/auth.py module.

Tests authentication and authorization utilities.
"""

import pytest
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from src.shared.auth import get_user_from_context


class TestGetUserFromContext:
    """Tests for get_user_from_context function."""

    def test_extracts_user_id_from_claims(self):
        """Should extract user ID from authorizer claims."""
        event = {"requestContext": {"authorizer": {"claims": {"sub": "user-123-abc"}}}}

        result = get_user_from_context(event)

        assert result == "user-123-abc"

    def test_extracts_user_id_from_principal_id(self):
        """Should fall back to principalId if claims.sub not present."""
        event = {"requestContext": {"authorizer": {"principalId": "user-456-def"}}}

        result = get_user_from_context(event)

        assert result == "user-456-def"

    def test_raises_error_when_no_user_id(self):
        """Should raise AuthenticationError when user ID not found."""
        event = {"requestContext": {"authorizer": {}}}

        with pytest.raises(UnauthorizedError) as exc_info:
            get_user_from_context(event)

        assert "User identity not found" in str(exc_info.value.msg)

    def test_raises_error_when_no_authorizer(self):
        """Should raise AuthenticationError when authorizer missing."""
        event = {"requestContext": {}}

        with pytest.raises(UnauthorizedError) as exc_info:
            get_user_from_context(event)

        assert "User identity not found" in str(exc_info.value.msg)

    def test_raises_error_when_no_request_context(self):
        """Should raise AuthenticationError when requestContext missing."""
        event = {}

        with pytest.raises(UnauthorizedError) as exc_info:
            get_user_from_context(event)

        assert "User identity not found" in str(exc_info.value.msg)

    def test_prefers_claims_sub_over_principal_id(self):
        """Should prefer claims.sub over principalId."""
        event = {
            "requestContext": {
                "authorizer": {"claims": {"sub": "claims-user"}, "principalId": "principal-user"}
            }
        }

        result = get_user_from_context(event)

        assert result == "claims-user"
