"""
Vault management route handlers for Cortex API.

This module implements vault-related endpoints including vault creation
and vault salt retrieval for key derivation.

Requirements: 14.4, 22.1, 22.2, 22.3
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from src.api.routes.base_route import BaseRoute
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.logger import get_logger
from src.shared.models import CreateVaultRequest, CreateVaultResponse, GetVaultSaltResponse

logger = get_logger("vault_routes")


class CreateVaultRoute(BaseRoute):
    """Handle vault creation with vault salt."""

    def __init__(self, vault_service: VaultService):
        """
        Initialize create vault route.

        Args:
            vault_service: Optional VaultService instance for dependency injection
        """
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/vaults")
        def handle(
            request: CreateVaultRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create new vault with vault salt.

            This endpoint creates a new vault for the authenticated user.
            The vault salt is either provided by the client or generated
            server-side using a cryptographically secure RNG.

            Returns:
                Vault ID, vault salt, and creation timestamp

            Requirements: 14.4, 22.1, 22.2, 22.3
            """
            logger.info("Creating vault", user_id=user_id)

            result = self.vault_service.create_vault(user_id=user_id, vault_salt=request.vault_salt)

            # Build response
            response = CreateVaultResponse(
                vault_id=result["vault_id"],
                created_at=datetime.fromtimestamp(result["created_at"]),
            )

            logger.info(
                "Vault created successfully",
                user_id=user_id,
                vault_id=result["vault_id"],
            )

            return response.model_dump(mode="json")


class GetVaultSaltRoute(BaseRoute):
    """Handle vault salt retrieval for key derivation."""

    def __init__(self, vault_service: VaultService):
        """
        Initialize get vault salt route.

        Args:
            vault_service: Optional VaultService instance for dependency injection
        """
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/vaults/{vault_id}/salt")
        def handle(
            vault_id: str,
            user_id: str = Depends(get_current_user),
        ):
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
            logger.info("Retrieving vault salt", user_id=user_id, vault_id=vault_id)

            vault_salt = self.vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

            # Build response
            response = GetVaultSaltResponse(vault_id=vault_id, vault_salt=vault_salt)

            logger.info(
                "Vault salt retrieved successfully",
                user_id=user_id,
                vault_id=vault_id,
            )

            return response.model_dump(mode="json")
