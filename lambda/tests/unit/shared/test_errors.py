"""
Unit tests for shared/errors.py module.

Tests error classes and error handling utilities.
"""

from datetime import datetime

from src.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    CortexError,
    ErrorCode,
    PasswordBreachedError,
    PasswordTooWeakError,
    RateLimitError,
    RecoveryCodeInvalidError,
    ResourceNotFoundError,
    ShareExpiredError,
    ShareRevokedError,
    StorageError,
    ValidationError,
    VaultSaltNotFoundError,
    format_error_response,
    get_http_status_code,
    sanitize_error_message,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_authentication_codes(self):
        """Should have authentication error codes."""
        assert ErrorCode.AUTHENTICATION_REQUIRED.value == "AUTHENTICATION_REQUIRED"
        assert ErrorCode.AUTHENTICATION_FAILED.value == "AUTHENTICATION_FAILED"

    def test_authorization_codes(self):
        """Should have authorization error codes."""
        assert ErrorCode.AUTHORIZATION_FAILED.value == "AUTHORIZATION_FAILED"
        assert ErrorCode.SHARE_EXPIRED.value == "SHARE_EXPIRED"
        assert ErrorCode.SHARE_REVOKED.value == "SHARE_REVOKED"

    def test_not_found_codes(self):
        """Should have not found error codes."""
        assert ErrorCode.RESOURCE_NOT_FOUND.value == "RESOURCE_NOT_FOUND"
        assert ErrorCode.VAULT_SALT_NOT_FOUND.value == "VAULT_SALT_NOT_FOUND"

    def test_validation_codes(self):
        """Should have validation error codes."""
        assert ErrorCode.INVALID_REQUEST.value == "INVALID_REQUEST"
        assert ErrorCode.PASSWORD_TOO_WEAK.value == "PASSWORD_TOO_WEAK"
        assert ErrorCode.PASSWORD_BREACHED.value == "PASSWORD_BREACHED"
        assert ErrorCode.RECOVERY_CODE_INVALID.value == "RECOVERY_CODE_INVALID"

    def test_rate_limit_code(self):
        """Should have rate limit error code."""
        assert ErrorCode.RATE_LIMIT_EXCEEDED.value == "RATE_LIMIT_EXCEEDED"

    def test_server_error_codes(self):
        """Should have server error codes."""
        assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
        assert ErrorCode.STORAGE_ERROR.value == "STORAGE_ERROR"


class TestCortexError:
    """Tests for CortexError base class."""

    def test_creates_error_with_all_params(self):
        """Should create error with all parameters."""
        error = CortexError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Something went wrong",
            status_code=500,
            details={"key": "value"},
        )

        assert error.code == ErrorCode.INTERNAL_ERROR
        assert error.message == "Something went wrong"
        assert error.status_code == 500
        assert error.details == {"key": "value"}
        assert str(error) == "Something went wrong"

    def test_creates_error_with_defaults(self):
        """Should create error with default values."""
        error = CortexError(code=ErrorCode.INTERNAL_ERROR, message="Error message")

        assert error.status_code == 500
        assert error.details == {}

    def test_is_exception(self):
        """Should be an Exception subclass."""
        error = CortexError(code=ErrorCode.INTERNAL_ERROR, message="Test")

        assert isinstance(error, Exception)


class TestAuthenticationError:
    """Tests for AuthenticationError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = AuthenticationError()

        assert error.code == ErrorCode.AUTHENTICATION_REQUIRED
        assert error.message == "Authentication required"
        assert error.status_code == 401

    def test_custom_message(self):
        """Should accept custom message."""
        error = AuthenticationError(message="Token expired")

        assert error.message == "Token expired"
        assert error.status_code == 401

    def test_custom_code(self):
        """Should accept custom error code."""
        error = AuthenticationError(message="Auth failed", code=ErrorCode.AUTHENTICATION_FAILED)

        assert error.code == ErrorCode.AUTHENTICATION_FAILED


class TestAuthorizationError:
    """Tests for AuthorizationError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = AuthorizationError()

        assert error.code == ErrorCode.AUTHORIZATION_FAILED
        assert error.message == "Access denied"
        assert error.status_code == 403

    def test_custom_message(self):
        """Should accept custom message."""
        error = AuthorizationError(message="Insufficient permissions")

        assert error.message == "Insufficient permissions"


class TestResourceNotFoundError:
    """Tests for ResourceNotFoundError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = ResourceNotFoundError()

        assert error.code == ErrorCode.RESOURCE_NOT_FOUND
        assert error.message == "Resource not found"
        assert error.status_code == 404

    def test_custom_resource_type(self):
        """Should accept custom resource type."""
        error = ResourceNotFoundError(resource_type="File")

        assert error.message == "File not found"

    def test_custom_code(self):
        """Should accept custom error code."""
        error = ResourceNotFoundError(
            resource_type="Vault salt", code=ErrorCode.VAULT_SALT_NOT_FOUND
        )

        assert error.code == ErrorCode.VAULT_SALT_NOT_FOUND


class TestValidationError:
    """Tests for ValidationError class."""

    def test_creates_with_message(self):
        """Should create with message."""
        error = ValidationError(message="Invalid input")

        assert error.code == ErrorCode.INVALID_REQUEST
        assert error.message == "Invalid input"
        assert error.status_code == 400

    def test_custom_code(self):
        """Should accept custom error code."""
        error = ValidationError(message="Password too weak", code=ErrorCode.PASSWORD_TOO_WEAK)

        assert error.code == ErrorCode.PASSWORD_TOO_WEAK


class TestRateLimitError:
    """Tests for RateLimitError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = RateLimitError()

        assert error.code == ErrorCode.RATE_LIMIT_EXCEEDED
        assert error.message == "Rate limit exceeded"
        assert error.status_code == 429

    def test_custom_message(self):
        """Should accept custom message."""
        error = RateLimitError(message="Too many requests, try again later")

        assert error.message == "Too many requests, try again later"


class TestStorageError:
    """Tests for StorageError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = StorageError()

        assert error.code == ErrorCode.STORAGE_ERROR
        assert error.message == "Storage operation failed"
        assert error.status_code == 500

    def test_custom_message(self):
        """Should accept custom message."""
        error = StorageError(message="DynamoDB write failed")

        assert error.message == "DynamoDB write failed"


class TestShareExpiredError:
    """Tests for ShareExpiredError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = ShareExpiredError()

        assert error.code == ErrorCode.SHARE_EXPIRED
        assert error.message == "Share link has expired"
        assert error.status_code == 403


class TestShareRevokedError:
    """Tests for ShareRevokedError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = ShareRevokedError()

        assert error.code == ErrorCode.SHARE_REVOKED
        assert error.message == "Share has been revoked"
        assert error.status_code == 403


class TestRecoveryCodeInvalidError:
    """Tests for RecoveryCodeInvalidError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = RecoveryCodeInvalidError()

        assert error.code == ErrorCode.RECOVERY_CODE_INVALID
        assert error.message == "Recovery code is invalid or already used"
        assert error.status_code == 401


class TestPasswordTooWeakError:
    """Tests for PasswordTooWeakError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = PasswordTooWeakError()

        assert error.code == ErrorCode.PASSWORD_TOO_WEAK
        assert error.message == "Password does not meet strength requirements"
        assert error.status_code == 400


class TestPasswordBreachedError:
    """Tests for PasswordBreachedError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = PasswordBreachedError()

        assert error.code == ErrorCode.PASSWORD_BREACHED
        assert error.message == "Password found in breach database"
        assert error.status_code == 400


class TestVaultSaltNotFoundError:
    """Tests for VaultSaltNotFoundError class."""

    def test_default_values(self):
        """Should have correct default values."""
        error = VaultSaltNotFoundError()

        assert error.code == ErrorCode.VAULT_SALT_NOT_FOUND
        assert error.message == "Vault salt not found"
        assert error.status_code == 404


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message function."""

    def test_returns_cortex_error_message(self):
        """Should return message from CortexError."""
        error = AuthenticationError(message="Custom auth error")

        result = sanitize_error_message("original message", error)

        assert result == "Custom auth error"

    def test_returns_generic_for_unknown_error(self):
        """Should return generic message for unknown errors."""
        error = ValueError("Internal details")

        result = sanitize_error_message("Internal details", error)

        assert result == "An internal error occurred"

    def test_returns_generic_for_exception(self):
        """Should return generic message for base Exception."""
        error = Exception("Some internal error")

        result = sanitize_error_message("Some internal error", error)

        assert result == "An internal error occurred"


class TestFormatErrorResponse:
    """Tests for format_error_response function."""

    def test_formats_cortex_error(self):
        """Should format CortexError correctly."""
        error = AuthenticationError(message="Token expired")

        result = format_error_response(error, "req-123")

        assert result["error"]["code"] == "AUTHENTICATION_REQUIRED"
        assert result["error"]["message"] == "Token expired"
        assert result["error"]["requestId"] == "req-123"
        assert "timestamp" in result["error"]

    def test_formats_unknown_error(self):
        """Should format unknown error with generic message."""
        error = ValueError("Internal error details")

        result = format_error_response(error, "req-456")

        assert result["error"]["code"] == "INTERNAL_ERROR"
        assert result["error"]["message"] == "An internal error occurred"
        assert result["error"]["requestId"] == "req-456"

    def test_excludes_details_by_default(self):
        """Should exclude details by default."""
        error = CortexError(
            code=ErrorCode.INTERNAL_ERROR, message="Error", details={"sensitive": "data"}
        )

        result = format_error_response(error, "req-789")

        assert "details" not in result["error"]

    def test_includes_details_when_requested(self):
        """Should include details when include_details=True."""
        error = CortexError(
            code=ErrorCode.INTERNAL_ERROR, message="Error", details={"debug": "info"}
        )

        result = format_error_response(error, "req-789", include_details=True)

        assert result["error"]["details"] == {"debug": "info"}

    def test_timestamp_format(self):
        """Should include ISO format timestamp with Z suffix."""
        error = AuthenticationError()

        result = format_error_response(error, "req-123")

        timestamp = result["error"]["timestamp"]
        assert timestamp.endswith("Z")
        # Should be parseable as ISO format
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestGetHttpStatusCode:
    """Tests for get_http_status_code function."""

    def test_returns_cortex_error_status(self):
        """Should return status code from CortexError."""
        error = AuthenticationError()
        assert get_http_status_code(error) == 401

        error = AuthorizationError()
        assert get_http_status_code(error) == 403

        error = ResourceNotFoundError()
        assert get_http_status_code(error) == 404

        error = ValidationError("Invalid")
        assert get_http_status_code(error) == 400

        error = RateLimitError()
        assert get_http_status_code(error) == 429

        error = StorageError()
        assert get_http_status_code(error) == 500

    def test_returns_500_for_unknown_error(self):
        """Should return 500 for unknown errors."""
        error = ValueError("Unknown error")

        result = get_http_status_code(error)

        assert result == 500

    def test_returns_500_for_base_exception(self):
        """Should return 500 for base Exception."""
        error = Exception("Generic error")

        result = get_http_status_code(error)

        assert result == 500
