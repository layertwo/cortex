"""
Domain exceptions for Cortex API.

These exceptions are framework-agnostic and used throughout the service
and route layers. They are mapped to HTTP responses by FastAPI exception
handlers.
"""


class CortexError(Exception):
    """Base exception for all Cortex domain errors."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "Internal server error"):
        self.message = message
        super().__init__(message)


class BadRequestError(CortexError):
    status_code = 400
    code = "BAD_REQUEST"


class UnauthorizedError(CortexError):
    status_code = 401
    code = "AUTHENTICATION_REQUIRED"


class NotFoundError(CortexError):
    status_code = 404
    code = "NOT_FOUND"


class InternalError(CortexError):
    status_code = 500
    code = "INTERNAL_ERROR"


class ShareRevokedError(CortexError):
    """Raised when attempting to access a revoked share."""

    status_code = 410
    code = "SHARE_REVOKED"

    def __init__(self, message: str = "Share has been revoked"):
        super().__init__(message)


class ShareExpiredError(CortexError):
    """Raised when attempting to access an expired share."""

    status_code = 410
    code = "SHARE_EXPIRED"

    def __init__(self, message: str = "Share has expired"):
        super().__init__(message)


class ConflictError(CortexError):
    """Raised when a request conflicts with the current state of a resource."""

    status_code = 409
    code = "CONFLICT"

    def __init__(self, message: str = "Conflict"):
        super().__init__(message)


class RateLimitExceededError(CortexError):
    """Raised when a rate limit is exceeded."""

    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 3600):
        self.retry_after = retry_after
        super().__init__(message)
