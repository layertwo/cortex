"""
Unit tests for shared/auth.py module.

Tests authentication and authorization utilities.
"""

import pytest
from aws_lambda_powertools.event_handler.exceptions import ForbiddenError, UnauthorizedError

from src.shared.auth import (
    extract_bearer_token,
    get_user_email_from_context,
    get_user_from_context,
    get_vault_id_from_user,
    require_authentication,
    validate_cognito_token_claims,
    verify_user_owns_resource,
    verify_user_owns_vault,
)


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


class TestGetUserEmailFromContext:
    """Tests for get_user_email_from_context function."""

    def test_extracts_email_from_claims(self):
        """Should extract email from authorizer claims."""
        event = {"requestContext": {"authorizer": {"claims": {"email": "user@example.com"}}}}

        result = get_user_email_from_context(event)

        assert result == "user@example.com"

    def test_returns_none_when_no_email(self):
        """Should return None when email not in claims."""
        event = {"requestContext": {"authorizer": {"claims": {}}}}

        result = get_user_email_from_context(event)

        assert result is None

    def test_returns_none_when_no_claims(self):
        """Should return None when claims missing."""
        event = {"requestContext": {"authorizer": {}}}

        result = get_user_email_from_context(event)

        assert result is None

    def test_returns_none_when_no_authorizer(self):
        """Should return None when authorizer missing."""
        event = {"requestContext": {}}

        result = get_user_email_from_context(event)

        assert result is None

    def test_returns_none_when_empty_event(self):
        """Should return None for empty event."""
        event = {}

        result = get_user_email_from_context(event)

        assert result is None


class TestVerifyUserOwnsVault:
    """Tests for verify_user_owns_vault function."""

    def test_passes_when_vault_ids_match(self):
        """Should not raise when vault IDs match."""
        verify_user_owns_vault("user-123", "vault-abc", "vault-abc")
        # No exception means success

    def test_raises_when_vault_ids_differ(self):
        """Should raise AuthorizationError when vault IDs differ."""
        with pytest.raises(ForbiddenError) as exc_info:
            verify_user_owns_vault("user-123", "vault-abc", "vault-xyz")

        assert "Access denied to vault" in str(exc_info.value.msg)


class TestVerifyUserOwnsResource:
    """Tests for verify_user_owns_resource function."""

    def test_passes_when_user_ids_match(self):
        """Should not raise when user IDs match."""
        verify_user_owns_resource("user-123", "user-123")
        # No exception means success

    def test_raises_when_user_ids_differ(self):
        """Should raise AuthorizationError when user IDs differ."""
        with pytest.raises(ForbiddenError) as exc_info:
            verify_user_owns_resource("user-123", "user-456")

        assert "Access denied to resource" in str(exc_info.value.msg)


class TestExtractBearerToken:
    """Tests for extract_bearer_token function."""

    def test_extracts_token_from_authorization_header(self):
        """Should extract token from Authorization header."""
        event = {"headers": {"Authorization": "Bearer my-jwt-token-123"}}

        result = extract_bearer_token(event)

        assert result == "my-jwt-token-123"

    def test_extracts_token_from_lowercase_header(self):
        """Should extract token from lowercase authorization header."""
        event = {"headers": {"authorization": "Bearer lowercase-token"}}

        result = extract_bearer_token(event)

        assert result == "lowercase-token"

    def test_returns_none_when_no_bearer_prefix(self):
        """Should return None when Authorization header lacks Bearer prefix."""
        event = {"headers": {"Authorization": "Basic some-basic-auth"}}

        result = extract_bearer_token(event)

        assert result is None

    def test_returns_none_when_no_authorization_header(self):
        """Should return None when Authorization header missing."""
        event = {"headers": {}}

        result = extract_bearer_token(event)

        assert result is None

    def test_returns_none_when_no_headers(self):
        """Should return None when headers missing."""
        event = {}

        result = extract_bearer_token(event)

        assert result is None

    def test_handles_empty_bearer_token(self):
        """Should return empty string for 'Bearer ' with no token."""
        event = {"headers": {"Authorization": "Bearer "}}

        result = extract_bearer_token(event)

        assert result == ""


class TestValidateCognitoTokenClaims:
    """Tests for validate_cognito_token_claims function."""

    def test_returns_true_for_valid_claims(self):
        """Should return True when all required claims present."""
        claims = {
            "sub": "user-123",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/pool-id",
            "exp": 1234567890,
            "iat": 1234567800,
        }

        result = validate_cognito_token_claims(claims)

        assert result is True

    def test_returns_false_when_sub_missing(self):
        """Should return False when sub claim missing."""
        claims = {
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/pool-id",
            "exp": 1234567890,
            "iat": 1234567800,
        }

        result = validate_cognito_token_claims(claims)

        assert result is False

    def test_returns_false_when_iss_missing(self):
        """Should return False when iss claim missing."""
        claims = {"sub": "user-123", "exp": 1234567890, "iat": 1234567800}

        result = validate_cognito_token_claims(claims)

        assert result is False

    def test_returns_false_when_exp_missing(self):
        """Should return False when exp claim missing."""
        claims = {
            "sub": "user-123",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/pool-id",
            "iat": 1234567800,
        }

        result = validate_cognito_token_claims(claims)

        assert result is False

    def test_returns_false_when_iat_missing(self):
        """Should return False when iat claim missing."""
        claims = {
            "sub": "user-123",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/pool-id",
            "exp": 1234567890,
        }

        result = validate_cognito_token_claims(claims)

        assert result is False

    def test_returns_false_for_empty_claims(self):
        """Should return False for empty claims dict."""
        claims = {}

        result = validate_cognito_token_claims(claims)

        assert result is False

    def test_accepts_additional_claims(self):
        """Should accept claims with additional fields."""
        claims = {
            "sub": "user-123",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/pool-id",
            "exp": 1234567890,
            "iat": 1234567800,
            "email": "user@example.com",
            "custom:role": "admin",
        }

        result = validate_cognito_token_claims(claims)

        assert result is True


class TestGetVaultIdFromUser:
    """Tests for get_vault_id_from_user function."""

    def test_returns_vault_id_with_prefix(self):
        """Should return vault ID with 'vault-' prefix."""
        result = get_vault_id_from_user("user-123")

        assert result == "vault-user-123"

    def test_handles_uuid_user_id(self):
        """Should handle UUID-style user IDs."""
        result = get_vault_id_from_user("550e8400-e29b-41d4-a716-446655440000")

        assert result == "vault-550e8400-e29b-41d4-a716-446655440000"


class TestRequireAuthentication:
    """Tests for require_authentication function."""

    def test_returns_user_id_when_authenticated(self):
        """Should return user ID when authentication succeeds."""
        event = {"requestContext": {"authorizer": {"claims": {"sub": "user-123"}}}}

        result = require_authentication(event)

        assert result == "user-123"

    def test_raises_when_not_authenticated(self):
        """Should raise AuthenticationError when not authenticated."""
        event = {"requestContext": {"authorizer": {}}}

        with pytest.raises(UnauthorizedError):
            require_authentication(event)
