"""
Vault management route handlers for Cortex API.

This module implements vault-related endpoints including vault creation
and vault salt retrieval for key derivation.

Requirements: 14.4, 22.1, 22.2, 22.3
"""

from datetime import datetime

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from pydantic import ValidationError as PydanticValidationError

from src.api.routes.base_route import BaseRoute
from src.api.services.vault_service import VaultService
from src.shared.auth import get_user_from_context
from src.shared.errors import ResourceNotFoundError, ValidationError
from src.shared.models import CreateVaultRequest, CreateVaultResponse, GetVaultSaltResponse

logger = Logger(child=True)


class CreateVaultRoute(BaseRoute):
    """Handle vault creation with vault salt."""

    def __init__(self, vault_service: VaultService):
        """
        Initialize create vault route.

        Args:
            vault_service: Optional VaultService instance for dependency injection
        """
        self.vault_service = vault_service

    def register(self, app: APIGatewayRestResolver) -> None:

        @app.post("/v1/vaults")
        def handle():
            """
            Create new vault with vault salt.

            This endpoint creates a new vault for the authenticated user.
            The vault salt is either provided by the client or generated
            server-side using a cryptographically secure RNG.

            Request Body:
                vault_salt: Optional 16-byte vault salt (base64-encoded in JSON)

            Returns:
                Vault ID, vault salt, and creation timestamp

            Requirements: 14.4, 22.1, 22.2, 22.3
            """
            try:
                # Extract user ID from API Gateway context
                user_id = get_user_from_context(app.current_event)

                # Parse request body
                body = app.current_event.json_body or {}
                request = CreateVaultRequest(**body)

                logger.info("Creating vault", extra={"user_id": user_id})

                result = self.vault_service.create_vault(
                    user_id=user_id, vault_salt=request.vault_salt
                )

                # Build response
                response = CreateVaultResponse(
                    vault_id=result["vault_id"],
                    created_at=datetime.fromtimestamp(result["created_at"]),
                )

                logger.info(
                    "Vault created successfully",
                    extra={"user_id": user_id, "vault_id": result["vault_id"]},
                )

                return response.model_dump(mode="json")

            except PydanticValidationError as e:
                logger.warning("Request validation failed", extra={"errors": e.errors()})
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body={
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": "Invalid request format",
                        }
                    },
                )

            except ValidationError as e:
                logger.warning("Vault creation validation failed", extra={"error": str(e)})
                raise
            except Exception as e:
                logger.error("Vault creation failed", extra={"error": str(e)})
                raise


class GetVaultSaltRoute(BaseRoute):
    """Handle vault salt retrieval for key derivation."""

    def __init__(self, vault_service: VaultService):
        """
        Initialize get vault salt route.

        Args:
            vault_service: Optional VaultService instance for dependency injection
        """
        self.vault_service = vault_service

    def register(self, app: APIGatewayRestResolver) -> None:

        @app.get("/v1/vaults/<vault_id>/salt")
        def handle(vault_id: str):
            """
            Retrieve vault salt for key derivation.

            This endpoint returns the vault salt needed by the client to
            derive the vault master key from the vault password using Argon2id.
            The salt is non-secret information that enables multi-device access.

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                Vault ID and 16-byte vault salt

            Requirements: 14.4, 22.3, 22.5
            """
            try:
                # Extract user ID from API Gateway context
                user_id = get_user_from_context(app.current_event)

                logger.info(
                    "Retrieving vault salt", extra={"user_id": user_id, "vault_id": vault_id}
                )

                vault_salt = self.vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

                # Build response
                response = GetVaultSaltResponse(vault_id=vault_id, vault_salt=vault_salt)

                logger.info(
                    "Vault salt retrieved successfully",
                    extra={"user_id": user_id, "vault_id": vault_id},
                )

                return response.model_dump(mode="json")

            except ResourceNotFoundError as e:
                logger.warning("Vault not found", extra={"vault_id": vault_id, "error": str(e)})
                raise
            except Exception as e:
                logger.error(
                    "Vault salt retrieval failed", extra={"vault_id": vault_id, "error": str(e)}
                )
                raise
