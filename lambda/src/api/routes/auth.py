"""
Authentication route handlers for Cortex API.

This module implements authentication-related endpoints including login,
token refresh, and account recovery.

Requirements: 3.1, 3.2, 19.2
"""

from typing import Optional

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from pydantic import BaseModel, Field

from src.api.routes.base_route import BaseRoute
from src.api.services.auth_service import AuthService
from src.shared.errors import ValidationError

logger = Logger(child=True)


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

    def __init__(self, auth_service: Optional[AuthService] = None):
        """
        Initialize login route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIGatewayRestResolver) -> None:
        auth_service = self.auth_service

        @app.post("/v1/auth/login")
        def handle():
            """
            Authenticate user with account password.

            This endpoint initiates authentication with AWS Cognito using
            the account password. The actual JWT validation is handled by
            API Gateway's Cognito authorizer.

            Request Body:
                email: User email address
                password: Account password (not vault password)

            Returns:
                Authentication result with tokens

            Requirements: 3.1, 3.2
            """
            try:
                body = app.current_event.json_body or {}
                request = LoginRequest(**body)

                logger.info(
                    "Login request received",
                    extra={
                        "email_domain": (
                            request.email.split("@")[-1] if "@" in request.email else "unknown"
                        )
                    },
                )

                # Use injected service or create placeholder response
                if auth_service:
                    result = auth_service.validate_login(request.email, request.password)
                else:
                    # Authentication is handled by Cognito via API Gateway
                    result = {
                        "message": "Authentication handled by Cognito authorizer",
                        "auth_type": "cognito",
                    }

                return LoginResponse(**result).model_dump()

            except ValidationError as e:
                logger.warning("Login validation failed", extra={"error": str(e)})
                raise
            except Exception as e:
                logger.error("Login failed", extra={"error": str(e)})
                raise


class RefreshRoute(BaseRoute):
    """Handle authentication token refresh."""

    def __init__(self, auth_service: Optional[AuthService] = None):
        """
        Initialize refresh route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIGatewayRestResolver) -> None:
        auth_service = self.auth_service

        @app.post("/v1/auth/refresh")
        def handle():
            """
            Refresh authentication credentials.

            This endpoint refreshes JWT tokens using a refresh token.
            The actual token refresh is handled by Cognito.

            Request Body:
                refresh_token: Refresh token from previous authentication

            Returns:
                New authentication tokens

            Requirements: 3.1, 3.2
            """
            try:
                body = app.current_event.json_body or {}
                request = RefreshRequest(**body)

                logger.info("Token refresh request received")

                # Use injected service or create placeholder response
                if auth_service:
                    result = auth_service.refresh_token(request.refresh_token)
                else:
                    # Token refresh is handled by Cognito
                    result = {
                        "message": "Token refresh handled by Cognito",
                        "auth_type": "cognito",
                    }

                return RefreshResponse(**result).model_dump()

            except ValidationError as e:
                logger.warning("Refresh validation failed", extra={"error": str(e)})
                raise
            except Exception as e:
                logger.error("Token refresh failed", extra={"error": str(e)})
                raise


class RecoverRoute(BaseRoute):
    """Handle account recovery with recovery code."""

    def __init__(self, auth_service: Optional[AuthService] = None):
        """
        Initialize recover route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIGatewayRestResolver) -> None:
        auth_service = self.auth_service

        @app.post("/v1/auth/recover")
        def handle():
            """
            Initiate account recovery with recovery code.

            This endpoint validates a recovery code and initiates the
            account password reset flow. Note: This does NOT affect
            vault encryption keys - only the account password.

            Request Body:
                email: User email address
                recovery_code: One of the user's recovery codes (format: XXXX-XXXX-XXXX-XXXX)

            Returns:
                Recovery session information

            Requirements: 19.2
            """
            try:
                body = app.current_event.json_body or {}
                request = RecoverRequest(**body)

                logger.info(
                    "Account recovery request received",
                    extra={
                        "email_domain": (
                            request.email.split("@")[-1] if "@" in request.email else "unknown"
                        )
                    },
                )

                # Use injected service or create placeholder response
                if auth_service:
                    result = auth_service.initiate_recovery(request.email, request.recovery_code)
                else:
                    # Placeholder response
                    result = {
                        "message": "Recovery code validation - service not configured",
                        "recovery_type": "account_password",
                    }

                return RecoverResponse(**result).model_dump()

            except ValidationError as e:
                logger.warning("Recovery validation failed", extra={"error": str(e)})
                raise
            except Exception as e:
                logger.error("Account recovery failed", extra={"error": str(e)})
                raise
