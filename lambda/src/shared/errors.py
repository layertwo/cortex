"""
Shared error handling module for Cortex Backup System.

This module defines custom exception classes for all error types,
error response formatting, and request ID tracking.

Requirements: 3.5, 8.3
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Standard error codes for API responses."""

    # Authentication errors (401)
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"

    # Authorization errors (403)
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    SHARE_EXPIRED = "SHARE_EXPIRED"
    SHARE_REVOKED = "SHARE_REVOKED"

    # Not found errors (404)
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    VAULT_SALT_NOT_FOUND = "VAULT_SALT_NOT_FOUND"

    # Validation errors (400)
    INVALID_REQUEST = "INVALID_REQUEST"
    PASSWORD_TOO_WEAK = "PASSWORD_TOO_WEAK"
    PASSWORD_BREACHED = "PASSWORD_BREACHED"
    RECOVERY_CODE_INVALID = "RECOVERY_CODE_INVALID"

    # Rate limiting (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"


class CortexError(Exception):
    """Base exception class for all Cortex errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a Cortex error.

        Args:
            code: Error code from ErrorCode enum
            message: Human-readable error message (sanitized)
            status_code: HTTP status code
            details: Optional additional details (will be sanitized)
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(CortexError):
    """Raised when authentication is required or fails."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: ErrorCode = ErrorCode.AUTHENTICATION_REQUIRED,
    ):
        super().__init__(code=code, message=message, status_code=401)


class AuthorizationError(CortexError):
    """Raised when user lacks permission for requested operation."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(code=ErrorCode.AUTHORIZATION_FAILED, message=message, status_code=403)


class ResourceNotFoundError(CortexError):
    """Raised when requested resource doesn't exist."""

    def __init__(
        self, resource_type: str = "Resource", code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND
    ):
        super().__init__(code=code, message=f"{resource_type} not found", status_code=404)


class ValidationError(CortexError):
    """Raised when request validation fails."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.INVALID_REQUEST):
        super().__init__(code=code, message=message, status_code=400)


class RateLimitError(CortexError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(code=ErrorCode.RATE_LIMIT_EXCEEDED, message=message, status_code=429)


class StorageError(CortexError):
    """Raised when S3 or DynamoDB operation fails."""

    def __init__(self, message: str = "Storage operation failed", error_code: Optional[str] = None):
        super().__init__(code=ErrorCode.STORAGE_ERROR, message=message, status_code=500)
        self.error_code = error_code  # Preserve original AWS error code


class ConditionalCheckFailedError(StorageError):
    """Raised when DynamoDB conditional check fails (item already exists or condition not met)."""

    def __init__(self, message: str = "Conditional check failed"):
        super().__init__(message=message, error_code="ConditionalCheckFailedException")


class ShareExpiredError(CortexError):
    """Raised when share link has expired."""

    def __init__(self, message: str = "Share link has expired"):
        super().__init__(code=ErrorCode.SHARE_EXPIRED, message=message, status_code=403)


class ShareRevokedError(CortexError):
    """Raised when share has been revoked."""

    def __init__(self, message: str = "Share has been revoked"):
        super().__init__(code=ErrorCode.SHARE_REVOKED, message=message, status_code=403)


class RecoveryCodeInvalidError(CortexError):
    """Raised when recovery code is invalid or already used."""

    def __init__(self, message: str = "Recovery code is invalid or already used"):
        super().__init__(code=ErrorCode.RECOVERY_CODE_INVALID, message=message, status_code=401)


class PasswordTooWeakError(CortexError):
    """Raised when password doesn't meet strength requirements."""

    def __init__(self, message: str = "Password does not meet strength requirements"):
        super().__init__(code=ErrorCode.PASSWORD_TOO_WEAK, message=message, status_code=400)


class PasswordBreachedError(CortexError):
    """Raised when password is found in breach database."""

    def __init__(self, message: str = "Password found in breach database"):
        super().__init__(code=ErrorCode.PASSWORD_BREACHED, message=message, status_code=400)


class VaultSaltNotFoundError(CortexError):
    """Raised when vault salt is not found."""

    def __init__(self, message: str = "Vault salt not found"):
        super().__init__(code=ErrorCode.VAULT_SALT_NOT_FOUND, message=message, status_code=404)


def sanitize_error_message(message: str, error: Exception) -> str:
    """
    Sanitize error message to prevent information leakage.

    Removes sensitive information like:
    - File paths
    - Internal implementation details
    - Stack traces
    - Database query details

    Args:
        message: Original error message
        error: Original exception

    Returns:
        Sanitized error message safe for client consumption
    """
    # For known Cortex errors, use the predefined message
    if isinstance(error, CortexError):
        return error.message

    # For unknown errors, return generic message
    # Never expose internal error details to clients
    return "An internal error occurred"


def format_error_response(
    error: Exception, request_id: str, include_details: bool = False
) -> Dict[str, Any]:
    """
    Format error as structured JSON response.

    Args:
        error: Exception to format
        request_id: Unique request ID for debugging
        include_details: Whether to include additional details (dev mode only)

    Returns:
        Structured error response dictionary
    """
    # Determine error code and status
    if isinstance(error, CortexError):
        code = error.code.value
        message = error.message
        details = error.details if include_details else {}
    else:
        code = ErrorCode.INTERNAL_ERROR.value
        message = sanitize_error_message(str(error), error)
        details = {}

    response = {
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    }

    # Add details only if explicitly requested (dev mode)
    if details and include_details:
        response["error"]["details"] = details

    return response


def get_http_status_code(error: Exception) -> int:
    """
    Get HTTP status code for an exception.

    Args:
        error: Exception to get status code for

    Returns:
        HTTP status code (default 500 for unknown errors)
    """
    if isinstance(error, CortexError):
        return error.status_code
    return 500
