"""
Account recovery route handlers for Cortex API.

This module implements recovery-related endpoints including recovery code
generation and validation.

Requirements: 19.1, 19.2, 19.3, 19.5
"""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from pydantic import BaseModel, Field

from src.api.routes.base_route import BaseRoute
from src.api.services.auth_service import AuthService
from src.shared.auth import get_user_from_context
from src.shared.errors import ValidationError

logger = Logger(child=True)


# Request/Response models
class GenerateRecoveryCodesRequest(BaseModel):
    """Request model for generating recovery codes."""

    pass  # User ID extracted from context


class GenerateRecoveryCodesResponse(BaseModel):
    """Response model for recovery code generation."""

    recovery_codes: list[str] = Field(..., description="List of recovery codes (displayed once)")
    generated_at: int = Field(..., description="Generation timestamp")


class ValidateRecoveryCodeRequest(BaseModel):
    """Request model for validating recovery code."""

    recovery_code: str = Field(..., description="Recovery code to validate")


class ValidateRecoveryCodeResponse(BaseModel):
    """Response model for recovery code validation."""

    valid: bool = Field(..., description="Whether code is valid")
    user_id: str = Field(..., description="User identifier")


class GenerateRecoveryCodesRoute(BaseRoute):
    """Handle recovery code generation."""

    def __init__(self, auth_service: AuthService):
        """
        Initialize generate recovery codes route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIGatewayRestResolver) -> None:

        @app.post("/v1/recovery/codes")
        def handle():
            """
            Generate account recovery codes.

            Generates 10 recovery codes in format XXXX-XXXX-XXXX-XXXX.
            Codes are hashed with SHA-256 before storage in DynamoDB.

            Returns:
                List of recovery codes (displayed once to user)

            Requirements: 19.1
            """
            try:
                # Extract user ID from API Gateway context
                user_id = get_user_from_context(app.current_event)

                logger.info("Generating recovery codes", extra={"user_id": user_id})

                # Generate recovery codes
                codes, timestamp = self.auth_service.generate_recovery_codes(user_id)

                logger.info(
                    "Recovery codes generated successfully",
                    extra={"user_id": user_id, "code_count": len(codes)},
                )

                return GenerateRecoveryCodesResponse(
                    recovery_codes=codes, generated_at=timestamp
                ).model_dump()

            except ValidationError as e:
                logger.warning(
                    "Recovery code generation validation failed", extra={"error": str(e)}
                )
                raise
            except Exception as e:
                logger.error("Recovery code generation failed", extra={"error": str(e)})
                raise


class ValidateRecoveryCodeRoute(BaseRoute):
    """Handle recovery code validation."""

    def __init__(self, auth_service: AuthService):
        """
        Initialize validate recovery code route.

        Args:
            auth_service: Optional AuthService instance for dependency injection
        """
        self.auth_service = auth_service

    def register(self, app: APIGatewayRestResolver) -> None:

        @app.post("/v1/recovery/validate")
        def handle():
            """
            Validate recovery code.

            Validates a recovery code and marks it as used if valid.
            Each code can only be used once.

            Request Body:
                recovery_code: Recovery code to validate (format: XXXX-XXXX-XXXX-XXXX)

            Returns:
                Validation result with user ID

            Requirements: 19.2, 19.3, 19.5
            """
            try:
                # Extract user ID from API Gateway context
                user_id = get_user_from_context(app.current_event)

                body = app.current_event.json_body or {}
                request = ValidateRecoveryCodeRequest(**body)

                logger.info("Validating recovery code", extra={"user_id": user_id})

                # Validate recovery code (marks as used if valid)
                is_valid = self.auth_service.validate_recovery_code(user_id, request.recovery_code)

                logger.info(
                    "Recovery code validation completed",
                    extra={"user_id": user_id, "valid": is_valid},
                )

                return ValidateRecoveryCodeResponse(valid=is_valid, user_id=user_id).model_dump()

            except ValidationError as e:
                logger.warning("Recovery code validation failed", extra={"error": str(e)})
                raise
            except Exception as e:
                logger.error("Recovery code validation error", extra={"error": str(e)})
                raise
