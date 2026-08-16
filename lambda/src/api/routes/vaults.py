"""
Vault management route handlers for Cortex API.

This module implements vault-related endpoints including vault creation
and vault salt retrieval for key derivation.

Request/response shapes come from the Smithy-generated models
(src.shared.generated.models): snake_case attrs with camelCase aliases, so
FastAPI serializes the camelCase wire contract the web client targets. Blob
fields are pydantic Base64Bytes — raw bytes Python-side, base64 on the wire —
so raw salt from the service is base64-encoded at construction.

Requirements: 14.4, 22.1, 22.2, 22.3
"""

import base64

from fastapi import APIRouter, Depends

from src.api.routes.base_route import BaseRoute
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.generated.models import (
    CreateVaultRequestContent,
    CreateVaultResponseContent,
    GetVaultResponseContent,
    GetVaultSaltResponseContent,
    UpdateVaultRotationRequestContent,
    UpdateVaultRotationResponseContent,
)
from src.shared.logger import get_logger

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
        @app.post("/v1/vaults", response_model=CreateVaultResponseContent)
        def handle(
            request: CreateVaultRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create new vault with a server-generated vault salt.

            The vault salt is always generated server-side with a
            cryptographically secure RNG (the contract no longer accepts a
            client-provided salt). The optional encrypted vault name is accepted
            but not yet persisted.

            Returns:
                Vault ID, vault salt (base64), and creation timestamp (epoch).

            Requirements: 14.4, 22.1, 22.2, 22.3
            """
            logger.info("Creating vault")

            # ponytail: encryptedName is in the contract but vault naming isn't
            # built yet — wire request.encrypted_name through when it ships.
            result = self.vault_service.create_vault(user_id=user_id)

            response = CreateVaultResponseContent(
                vault_id=result["vault_id"],
                vault_salt=base64.b64encode(result["vault_salt"]),
                created_at=result["created_at"],
            )

            logger.info(
                "Vault created successfully",
                vault_id=result["vault_id"],
            )

            return response


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
        @app.get("/v1/vaults/{vault_id}/salt", response_model=GetVaultSaltResponseContent)
        def handle(
            vault_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Retrieve vault salt for key derivation.

            Returns the vault salt the client needs to derive the vault master
            key from the vault password using Argon2id. The salt is non-secret
            and enables multi-device access.

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                The 16-byte vault salt (base64).

            Requirements: 14.4, 22.3, 22.5
            """
            logger.info("Retrieving vault salt", vault_id=vault_id)

            vault_salt = self.vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

            logger.info(
                "Vault salt retrieved successfully",
                vault_id=vault_id,
            )

            return GetVaultSaltResponseContent(vault_salt=base64.b64encode(vault_salt))


class GetVaultRoute(BaseRoute):
    """Handle vault retrieval including rotation state."""

    def __init__(self, vault_service: VaultService):
        """
        Initialize get vault route.

        Args:
            vault_service: VaultService instance for dependency injection
        """
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/vaults/{vault_id}", response_model=GetVaultResponseContent)
        def handle(vault_id: str, user_id: str = Depends(get_current_user)):
            """
            Retrieve the vault record, including vault password rotation state.

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                Vault metadata plus KEK version and rotation state/lock timestamp.
            """
            logger.info("Retrieving vault", vault_id=vault_id)

            vault = self.vault_service.get_vault(user_id=user_id, vault_id=vault_id)

            return GetVaultResponseContent(
                vault_id=vault["vault_id"],
                vault_salt=base64.b64encode(vault["vault_salt"]),
                created_at=vault["created_at"],
                updated_at=vault["updated_at"],
                kek_version=vault.get("kek_version"),
                rotation_state=vault.get("rotation_state"),
                rotation_locked_at=vault.get("rotation_locked_at"),
            )


class UpdateVaultRotationRoute(BaseRoute):
    """Handle rotation lock acquire/release (conditional write)."""

    def __init__(self, vault_service: VaultService):
        """
        Initialize update vault rotation route.

        Args:
            vault_service: VaultService instance for dependency injection
        """
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/vaults/{vault_id}/rotation", response_model=UpdateVaultRotationResponseContent
        )
        def handle(
            vault_id: str,
            request: UpdateVaultRotationRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Acquire or release the vault password rotation lock.

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                The resulting rotation state and lock timestamp (if any).

            Raises:
                ConflictError: If the conditional write fails (409)
            """
            logger.info(
                "Updating vault rotation state",
                vault_id=vault_id,
                action=request.action,
            )

            result = self.vault_service.update_vault_rotation(
                user_id=user_id,
                vault_id=vault_id,
                action=request.action,
                expected_state=request.expected_state,
                kek_version=request.kek_version,
                new_verifier=bytes(request.new_verifier) if request.new_verifier else None,
            )

            return UpdateVaultRotationResponseContent(
                rotation_state=result["rotation_state"],
                rotation_locked_at=result.get("rotation_locked_at"),
            )
