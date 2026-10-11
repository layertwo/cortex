"""
Vault management route handlers for Cortex API.

This module implements vault-related endpoints: create, list, name update,
retrieval, salt retrieval, and the password-rotation lock.

Request/response shapes come from the Smithy-generated models
(src.shared.generated.models): snake_case attrs with camelCase aliases, so
FastAPI serializes the camelCase wire contract the web client targets. Blob
fields are pydantic Base64Bytes — raw bytes Python-side, base64 on the wire —
so raw salt from the service is base64-encoded at construction.

Requirements: 14.4, 22.1, 22.2, 22.3
"""

import base64

from fastapi import APIRouter, Depends, Query

from src.api.routes.base_route import BaseRoute
from src.api.services.vault_deletion_service import VaultDeletionService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.exceptions import BadRequestError
from src.shared.generated.models import (
    CreateVaultResponseContent,
    DeleteVaultResponseContent,
    GetVaultResponseContent,
    GetVaultSaltResponseContent,
    ListVaultsResponseContent,
    UpdateVaultPasswordRequestContent,
    UpdateVaultPasswordResponseContent,
    UpdateVaultRequestContent,
    UpdateVaultResponseContent,
    UpdateVaultRotationRequestContent,
    UpdateVaultRotationResponseContent,
    VaultSummary,
    VmkEnvelope,
)
from src.shared.logger import get_logger
from src.shared.util import _encode_binary, to_bytes

logger = get_logger("vault_routes")


def _vmk_envelopes(vault: dict) -> list[VmkEnvelope]:
    """Build the wire VmkEnvelope list from the service's envelope dicts."""
    return [
        VmkEnvelope(
            vmk_version=env["vmk_version"],
            wrapped_vmk=_encode_binary(env.get("wrapped_vmk")),
            created_at=float(env["created_at"]),
        )
        for env in vault.get("vmk_envelopes") or []
    ]


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
        def handle(user_id: str = Depends(get_current_user)):
            """
            Create new vault with a server-generated vault salt.

            The vault salt is always generated server-side with a
            cryptographically secure RNG. The request has no body: the vault
            name is stored afterwards through UpdateVault, because its key
            derives from the salt this call returns.

            Returns:
                Vault ID, vault salt (base64), and creation timestamp (epoch).

            Requirements: 14.4, 22.1, 22.2, 22.3
            """
            logger.info("Creating vault")

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
                encrypted_name=_encode_binary(vault.get("encrypted_name")),
                created_at=vault["created_at"],
                updated_at=vault["updated_at"],
                current_vmk_version=vault["current_vmk_version"],
                envelope_version=vault["envelope_version"],
                vmk_envelopes=_vmk_envelopes(vault),
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

            ACQUIRE appends the new VMK envelope and bumps the version counters,
            taking the lock; RELEASE only flips the lock to IDLE and may store the
            re-encrypted name (the versions were already bumped by ACQUIRE).

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                The resulting rotation state, lock timestamp, and version counters.

            Raises:
                BadRequestError: ACQUIRE without expectedEnvelopeVersion, newVmkVersion
                    or wrappedNewVmk, or newVmkVersion not the current version plus one (400)
                NotFoundError: Unknown or unowned vault (404)
                ConflictError: The conditional write fails (409)
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
                expected_envelope_version=request.expected_envelope_version,
                new_vmk_version=request.new_vmk_version,
                wrapped_new_vmk=to_bytes(request.wrapped_new_vmk),
                new_encrypted_name=to_bytes(request.new_encrypted_name),
            )

            return UpdateVaultRotationResponseContent(
                rotation_state=result["rotation_state"],
                rotation_locked_at=result.get("rotation_locked_at"),
                current_vmk_version=result["current_vmk_version"],
                envelope_version=result["envelope_version"],
            )


class ListVaultsRoute(BaseRoute):
    """Handle listing the caller's vaults with what a device needs to unlock them."""

    def __init__(self, vault_service: VaultService):
        """Initialize list vaults route."""
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/vaults", response_model=ListVaultsResponseContent)
        def handle(
            page_size: int = Query(50, alias="pageSize", ge=10, le=100),
            next_token: str | None = Query(None, alias="nextToken", max_length=1024),
            user_id: str = Depends(get_current_user),
        ):
            """
            List the caller's vaults, excluding vaults being deleted.

            A page may be empty while nextToken is present (the deletion filter
            runs after Limit); clients page until nextToken is null.

            Returns:
                One page of VaultSummary entries and the next-page token.
            """
            vaults, next_page_token = self.vault_service.list_user_vaults(
                user_id=user_id, page_size=page_size, next_token=next_token
            )

            summaries = [
                VaultSummary(
                    vault_id=vault["vault_id"],
                    vault_salt=_encode_binary(vault["vault_salt"]),
                    encrypted_name=_encode_binary(vault.get("encrypted_name")),
                    created_at=float(vault["created_at"]),
                    updated_at=float(vault["updated_at"]),
                    current_vmk_version=int(vault["current_vmk_version"]),
                    rotation_state=vault["rotation_state"],
                )
                for vault in vaults
            ]

            logger.info("Listed vaults successfully", count=len(summaries))

            return ListVaultsResponseContent(vaults=summaries, next_token=next_page_token or None)


class UpdateVaultRoute(BaseRoute):
    """Handle storing the encrypted vault name."""

    def __init__(self, vault_service: VaultService):
        """Initialize update vault route."""
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.put("/v1/vaults/{vault_id}", response_model=UpdateVaultResponseContent)
        def handle(
            vault_id: str,
            request: UpdateVaultRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Store the encrypted vault name.

            encryptedName is required (400 otherwise).

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                Vault identifier and the new updatedAt timestamp.

            Raises:
                BadRequestError: If encryptedName is missing (400)
                NotFoundError: If the vault is unknown or unowned (404)
                ConflictError: If the vault is being deleted (409)
            """
            if request.encrypted_name is None:
                raise BadRequestError("Provide encryptedName")

            logger.info("Updating vault", vault_id=vault_id)

            result = self.vault_service.update_vault(
                user_id=user_id,
                vault_id=vault_id,
                encrypted_name=to_bytes(request.encrypted_name),
            )

            return UpdateVaultResponseContent(**result)


class UpdateVaultPasswordRoute(BaseRoute):
    """Handle replacing the vault's VMK envelopes after a password change."""

    def __init__(self, vault_service: VaultService):
        """Initialize update vault password route."""
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/vaults/{vault_id}/password", response_model=UpdateVaultPasswordResponseContent
        )
        def handle(
            vault_id: str,
            request: UpdateVaultPasswordRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Replace the vault's VMK envelopes (bootstrap or pure re-wrap).

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                The new envelopeVersion.

            Raises:
                NotFoundError: If the vault is unknown or unowned (404)
                ConflictError: If the version set would change, bootstrap is
                    malformed, or the guarded write loses a race (409)
            """
            logger.info("Updating vault password envelopes", vault_id=vault_id)

            result = self.vault_service.update_vault_password(
                user_id=user_id,
                vault_id=vault_id,
                expected_envelope_version=request.expected_envelope_version,
                envelopes=[
                    {
                        "vmk_version": int(env.vmk_version),
                        "wrapped_vmk": to_bytes(env.wrapped_vmk),
                        "created_at": int(env.created_at),
                    }
                    for env in request.vmk_envelopes
                ],
            )

            return UpdateVaultPasswordResponseContent(envelope_version=result["envelope_version"])


class DeleteVaultRoute(BaseRoute):
    """Handle resumable vault deletion (one bounded step per call)."""

    def __init__(self, vault_deletion_service: VaultDeletionService):
        """Initialize delete vault route."""
        self.vault_deletion_service = vault_deletion_service

    def register(self, app: APIRouter) -> None:
        @app.delete("/v1/vaults/{vault_id}", response_model=DeleteVaultResponseContent)
        def handle(vault_id: str, user_id: str = Depends(get_current_user)):
            """
            Run one bounded deletion step; call until deletionState is DELETED.

            Path Parameters:
                vault_id: Vault identifier

            Returns:
                DELETING while work remains, DELETED once the vault row is gone,
                plus the rows removed by this call.

            Raises:
                NotFoundError: Unknown, unowned, or already deleted vault (404)
                ConflictError: A live password change holds the vault (409)
            """
            logger.info("Deleting vault", vault_id=vault_id)

            result = self.vault_deletion_service.delete_vault(user_id=user_id, vault_id=vault_id)

            return DeleteVaultResponseContent(**result)
