"""
Domain exceptions for Cortex API.

These exceptions are framework-agnostic and used throughout the service
and route layers. They are mapped to HTTP responses by FastAPI exception
handlers.
"""


class CortexError(Exception):
    """Base exception for all Cortex domain errors."""

    status_code: int = 500

    def __init__(self, message: str = "Internal server error"):
        self.message = message
        super().__init__(message)


class BadRequestError(CortexError):
    status_code = 400


class UnauthorizedError(CortexError):
    status_code = 401


class NotFoundError(CortexError):
    status_code = 404


class InternalError(CortexError):
    status_code = 500
