"""
Authentication route handlers for Cortex API.

This module implements authentication-related endpoints including login,
token refresh, and account recovery.

Requirements: 3.1, 3.2, 19.2
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.api.routes.base_route import BaseRoute
from src.api.services.auth_service import AuthService
from src.shared.logger import get_logger

logger = get_logger("auth_routes")


# Request/Response models for authentication endpoints
class LoginRequest(BaseModel):
    """Request model for login endpoint."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Account password")


class LoginResponse(BaseModel):
    """Response model for login endpoint."""

    message: str = Field(..., description="Authentication status message")
    auth_type: str = Field(..., description="Authentication type used")


class RefreshRequest(BaseModel):
    """Request model for token refresh endpoint."""

    refresh_token: str = Field(..., description="Refresh token from previous authentication")


class RefreshResponse(BaseModel):
    """Response model for token refresh endpoint."""

    message: str = Field(..., description="Refresh status message")
    auth_type: str = Field(..., description="Authentication type used")


class RecoverRequest(BaseModel):
    """Request model for account recovery endpoint."""

    email: str = Field(..., description="User email address")
    recovery_code: str = Field(
        ..., description="Account recovery code (format: XXXX-XXXX-XXXX-XXXX)"
    )


class RecoverResponse(BaseModel):
    """Response model for account recovery endpoint."""

    message: str = Field(..., description="Recovery status message")
    recovery_type: str = Field(..., description="Type of recovery initiated")


class LoginRoute(BaseRoute):
    """Handle user login with account password."""

    def __init__(self, auth_service: AuthService):
        """
        Initialize login route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/auth/login")
        def handle(request: Request, login: LoginRequest):
            """
            Authenticate user with account password.

            This endpoint initiates authentication with AWS Cognito using
            the account password. The actual JWT validation is handled by
            API Gateway's Cognito authorizer.

            Returns:
                Authentication result with tokens

            Requirements: 3.1, 3.2
            """
            logger.info(
                "Login request received",
                email_domain=(login.email.split("@")[-1] if "@" in login.email else "unknown"),
            )

            result = self.auth_service.validate_login(login.email, login.password)

            return LoginResponse(**result).model_dump()


class RefreshRoute(BaseRoute):
    """Handle authentication token refresh."""

    def __init__(self, auth_service: AuthService):
        """
        Initialize refresh route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/auth/refresh")
        def handle(request: RefreshRequest):
            """
            Refresh authentication credentials.

            This endpoint refreshes JWT tokens using a refresh token.
            The actual token refresh is handled by Cognito.

            Returns:
                New authentication tokens

            Requirements: 3.1, 3.2
            """
            logger.info("Token refresh request received")

            result = self.auth_service.refresh_token(request.refresh_token)

            return RefreshResponse(**result).model_dump()


class RecoverRoute(BaseRoute):
    """Handle account recovery with recovery code."""

    def __init__(self, auth_service: AuthService):
        """
        Initialize recover route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/auth/recover")
        def handle(request: Request, recovery: RecoverRequest):
            """
            Initiate account recovery with recovery code.

            This endpoint validates a recovery code and initiates the
            account password reset flow. Note: This does NOT affect
            vault encryption keys - only the account password.

            Returns:
                Recovery session information

            Requirements: 19.2
            """
            logger.info(
                "Account recovery request received",
                email_domain=(
                    recovery.email.split("@")[-1] if "@" in recovery.email else "unknown"
                ),
            )

            result = self.auth_service.initiate_recovery(recovery.email, recovery.recovery_code)

            return RecoverResponse(**result).model_dump()
