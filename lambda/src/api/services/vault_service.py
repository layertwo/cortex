"""
Vault service layer for Cortex API.

This module implements business logic for vault management including
vault creation with salt generation, vault reads and listing, vault name
updates, deletion marks, and the rotation lock state machine.

Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5
"""

import secrets
import time
import uuid
from typing import Any, Dict, NoReturn, Optional

import boto3
from botocore.exceptions import ClientError

from src.shared.exceptions import BadRequestError, ConflictError, InternalError, NotFoundError
from src.shared.logger import get_logger
from src.shared.repository import encode_pagination_token, parse_pagination_token
from src.shared.util import to_bytes

logger = get_logger("vault_service")


# A rotation lock older than this is abandoned: ACQUIRE may steal it and
# DeleteVault may proceed past it (spec 4.3).
STALE_LOCK_SECONDS = 7 * 24 * 3600

# Wrapped-VMK envelope length: [version(1)][nonce(12)][ciphertext(32)+tag(16)].
WRAPPED_VMK_BYTES = 61


def _vault_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a vault row to the fields shared by get_vault and list_user_vaults."""
    return {
        "vault_id": item["vault_id"],
        "vault_salt": to_bytes(item.get("vault_salt")),
        "encrypted_name": to_bytes(item.get("encrypted_name")),
        "created_at": int(item["created_at"]),
        "updated_at": int(item.get("updated_at", item["created_at"])),
        "current_vmk_version": int(item.get("current_vmk_version", 0)),
        "envelope_version": int(item.get("envelope_version", 0)),
        "rotation_state": item.get("rotation_state", "IDLE"),
    }


def _envelope_dicts(item: Dict[str, Any]) -> list[Dict[str, Any]]:
    """Normalize a stored vmk_envelopes list to the service's envelope shape."""
    return [
        {
            "vmk_version": int(env["vmk_version"]),
            "wrapped_vmk": to_bytes(env.get("wrapped_vmk")),
            "created_at": int(env["created_at"]),
        }
        for env in item.get("vmk_envelopes") or []
    ]


class VaultService:
    """Service for vault management operations."""

    def __init__(self, session: boto3.Session, vaults_table_name: str):
        """
        Initialize vault service.

        Args:
            session: AWS session for DynamoDB access
            vaults_table_name: DynamoDB table name for vaults
        """
        self.vaults_table = session.resource("dynamodb").Table(vaults_table_name)

    def _read(self, key: dict, consistent: bool = False) -> Optional[dict]:
        """Read a vault row by key (Item, or None when absent)."""
        if consistent:
            return self.vaults_table.get_item(Key=key, ConsistentRead=True).get("Item")
        return self.vaults_table.get_item(Key=key).get("Item")

    def _live_item(self, user_id: str, vault_id: str) -> Optional[dict]:
        """Return the vault row, or None when missing or being deleted."""
        item = self._read({"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"})
        return None if not item or item.get("deletion_state") else item

    def create_vault(self, user_id: str, vault_salt: Optional[bytes] = None) -> Dict:
        """
        Create a new vault with a unique vault salt.

        The vault salt is a 16-byte cryptographically secure random value
        that is stored on the server and used by the client for key derivation.
        The salt is non-secret information that enables multi-device access.

        Args:
            user_id: User identifier
            vault_salt: Optional 16-byte vault salt (if not provided, will be generated)

        Returns:
            Dictionary containing vault_id, vault_salt, and created_at

        Raises:
            ValidationError: If vault_salt is provided but invalid
            StorageError: If DynamoDB operation fails

        Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5
        """
        # Generate vault ID
        vault_id = str(uuid.uuid4())

        # Generate or validate vault salt
        if vault_salt is None:
            # Generate 16-byte cryptographically secure random salt
            vault_salt = secrets.token_bytes(16)
            logger.info("Generated vault salt", **{"vault_id": vault_id})
        else:
            # Validate provided salt
            if not isinstance(vault_salt, bytes) or len(vault_salt) != 16:
                raise BadRequestError("Vault salt must be exactly 16 bytes")

        # Create timestamp
        created_at = int(time.time())

        # Build DynamoDB item
        item = {
            "PK": f"USER#{user_id}",
            "SK": f"VAULT#{vault_id}",
            "vault_id": vault_id,
            "user_id": user_id,
            "vault_salt": vault_salt,
            "created_at": created_at,
            "updated_at": created_at,
            # A fresh vault has no VMK enrolment yet; setup writes the first envelope
            # through UpdateVaultPassword. Both counters start at 0.
            "current_vmk_version": 0,
            "envelope_version": 0,
        }

        try:
            # Store vault in DynamoDB
            # Use condition to ensure vault_id uniqueness (though UUID collision is extremely unlikely)
            self.vaults_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )

            logger.info(
                "Vault created successfully",
                **{"vault_id": vault_id, "salt_length": len(vault_salt)},
            )

            return {"vault_id": vault_id, "vault_salt": vault_salt, "created_at": created_at}

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            if error_code == "ConditionalCheckFailedException":
                # Extremely unlikely UUID collision - retry with new ID
                logger.warning(
                    "Vault ID collision detected, retrying",
                    **{"vault_id": vault_id},
                )
                # Recursive retry (UUID collision is astronomically unlikely)
                return self.create_vault(user_id, vault_salt)

            logger.error(
                "Failed to create vault",
                **{"error": str(e), "vault_id": vault_id},
            )
            raise

    def get_vault_salt(self, user_id: str, vault_id: str) -> bytes:
        """
        Retrieve vault salt for key derivation.

        The vault salt is non-secret information that the client needs
        to derive the vault master key from the vault password using Argon2id.
        This enables multi-device access with the same vault password.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Returns:
            16-byte vault salt

        Raises:
            ResourceNotFoundError: If vault not found, not owned, or being deleted
            StorageError: If DynamoDB operation fails

        Requirements: 14.4, 22.3, 22.5
        """
        try:
            item = self._live_item(user_id, vault_id)

            if not item:
                logger.warning(
                    "Vault not found",
                    **{"vault_id": vault_id, "operation": "get_salt"},
                )
                raise NotFoundError("Vault not found")

            vault_salt = item.get("vault_salt")

            if not vault_salt:
                logger.error(
                    "Vault salt missing from vault item",
                    **{"vault_id": vault_id},
                )
                raise InternalError("Vault data integrity error: missing salt")

            vault_salt = to_bytes(vault_salt)

            # Validate salt format
            if not isinstance(vault_salt, bytes) or len(vault_salt) != 16:
                logger.error(
                    "Invalid vault salt format",
                    **{
                        "vault_id": vault_id,
                        "salt_type": type(vault_salt).__name__,
                        "salt_length": len(vault_salt) if isinstance(vault_salt, bytes) else None,
                    },
                )
                raise InternalError("Vault data integrity error: invalid salt format")

            logger.info(
                "Vault salt retrieved successfully",
                **{"vault_id": vault_id, "salt_length": len(vault_salt)},
            )

            return vault_salt

        except ClientError as e:
            logger.error(
                "Failed to retrieve vault salt",
                **{"error": str(e), "vault_id": vault_id},
            )
            raise

    def vault_exists(self, user_id: str, vault_id: str) -> bool:
        """
        Check if a vault exists for a user and is not being deleted.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Returns:
            True if the vault exists and has no deletion_state, False otherwise
        """
        try:
            return self._live_item(user_id, vault_id) is not None
        except ClientError as e:
            logger.error(
                "Failed to check vault existence",
                **{"error": str(e), "vault_id": vault_id},
            )
            raise NotFoundError("Vault not found")

    def list_user_vaults(
        self, user_id: str, page_size: int = 50, next_token: Optional[str] = None
    ) -> tuple[list[Dict[str, Any]], Optional[str]]:
        """
        List one page of the user's vaults, skipping vaults that are being deleted.

        Args:
            user_id: User identifier
            page_size: DynamoDB Limit for the page
            next_token: Opaque token from a previous page

        Returns:
            (vaults, next_token). A page may be empty while next_token is set
            because DynamoDB applies the deletion_state filter after Limit.

        Raises:
            StorageError: If DynamoDB operation fails
        """
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
            "FilterExpression": "attribute_not_exists(deletion_state)",
            "ExpressionAttributeValues": {":pk": f"USER#{user_id}", ":sk_prefix": "VAULT#"},
            "Limit": page_size,
        }
        start_key = parse_pagination_token(next_token)
        if start_key:
            kwargs["ExclusiveStartKey"] = start_key

        try:
            response = self.vaults_table.query(**kwargs)
        except ClientError as e:
            logger.error("Failed to list user vaults", **{"error": str(e)})
            raise

        vaults = [_vault_summary(item) for item in response.get("Items", [])]
        logger.info("Listed user vaults", **{"count": len(vaults)})
        return vaults, encode_pagination_token(response.get("LastEvaluatedKey"))

    def get_vault(self, user_id: str, vault_id: str) -> Dict:
        """
        Retrieve the vault record, including its VMK envelopes and rotation state.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Returns:
            Dictionary with vault_id, vault_salt, encrypted_name, created_at,
            updated_at, current_vmk_version, envelope_version, vmk_envelopes
            (list of {vmk_version, wrapped_vmk, created_at}), rotation_state,
            and rotation_locked_at.

        Raises:
            NotFoundError: If the vault is missing, unowned, or being deleted
        """
        item = self._live_item(user_id, vault_id)

        if not item:
            logger.warning(
                "Vault not found",
                **{"vault_id": vault_id, "operation": "get_vault"},
            )
            raise NotFoundError("Vault not found")

        vault = _vault_summary(item)
        vault["vmk_envelopes"] = _envelope_dicts(item)
        vault["rotation_locked_at"] = (
            int(item["rotation_locked_at"]) if item.get("rotation_locked_at") is not None else None
        )
        return vault

    def update_vault(
        self,
        user_id: str,
        vault_id: str,
        encrypted_name: Optional[bytes] = None,
    ) -> Dict:
        """
        Store the encrypted vault name.

        Args:
            user_id: User identifier
            vault_id: Vault identifier
            encrypted_name: Vault name encrypted under the vault metadata key

        Returns:
            Dictionary with vault_id and updated_at.

        Raises:
            NotFoundError: If the vault is missing or unowned
            ConflictError: If the vault is being deleted
        """
        key = {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
        now = int(time.time())
        update_expr = "SET updated_at = :now"
        values: Dict[str, Any] = {":now": now}
        if encrypted_name is not None:
            update_expr += ", encrypted_name = :name"
            values[":name"] = encrypted_name

        try:
            self.vaults_table.update_item(
                Key=key,
                UpdateExpression=update_expr,
                ConditionExpression="attribute_exists(PK) AND attribute_not_exists(deletion_state)",
                ExpressionAttributeValues=values,
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                logger.error("Failed to update vault", **{"error": str(e), "vault_id": vault_id})
                raise
            # Disambiguate the failed condition with one read.
            if not self._read(key):
                raise NotFoundError("Vault not found") from e
            logger.warning("Vault update rejected, vault is being deleted", vault_id=vault_id)
            raise ConflictError("Vault is being deleted") from e

        logger.info("Vault updated", **{"vault_id": vault_id})
        return {"vault_id": vault_id, "updated_at": now}

    def update_vault_password(
        self,
        user_id: str,
        vault_id: str,
        expected_envelope_version: int,
        envelopes: list[Dict[str, Any]],
    ) -> Dict:
        """
        Replace the vault's VMK envelopes after a vault password change.

        A pure re-wrap: the caller submits a fresh envelope for every version
        already stored, changing only wrapped_vmk/created_at and leaving
        current_vmk_version alone. Bootstrap (empty stored set and
        expected_envelope_version 0) stores exactly one version-1 envelope and
        enrols VMK version 1.

        Args:
            user_id: User identifier
            vault_id: Vault identifier
            expected_envelope_version: Envelope version the caller last read
            envelopes: Full envelope set ({vmk_version, wrapped_vmk, created_at})

        Returns:
            Dictionary with the new envelope_version.

        Raises:
            NotFoundError: If the vault is missing or being deleted
            ConflictError: If the submitted version set differs from the stored
                set, bootstrap is malformed, or the guarded write loses a race
        """
        key = {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
        item = self._read(key, consistent=True)
        if not item or item.get("deletion_state"):
            logger.warning(
                "Vault not found",
                **{"vault_id": vault_id, "operation": "update_vault_password"},
            )
            raise NotFoundError("Vault not found")

        stored_versions = {int(env["vmk_version"]) for env in item.get("vmk_envelopes") or []}
        submitted_versions = {int(env["vmk_version"]) for env in envelopes}

        update_expr = "SET vmk_envelopes = :env, envelope_version = :next"
        values: Dict[str, Any] = {
            ":env": envelopes,
            ":next": expected_envelope_version + 1,
            ":expected": expected_envelope_version,
        }

        if not stored_versions:
            if expected_envelope_version != 0 or submitted_versions != {1} or len(envelopes) != 1:
                logger.warning(
                    "Malformed vault password bootstrap",
                    vault_id=vault_id,
                )
                raise ConflictError("Bootstrap writes exactly one version 1 envelope")
            update_expr += ", current_vmk_version = :cur"
            values[":cur"] = 1
        elif submitted_versions != stored_versions:
            logger.warning(
                "Vault password update would change the VMK version set",
                vault_id=vault_id,
            )
            raise ConflictError("A vault password change cannot add or drop a VMK version")

        try:
            self.vaults_table.update_item(
                Key=key,
                UpdateExpression=update_expr,
                ConditionExpression=(
                    "envelope_version = :expected AND attribute_not_exists(deletion_state)"
                ),
                ExpressionAttributeValues=values,
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                logger.error(
                    "Failed to update vault password envelopes",
                    **{"error": str(e), "vault_id": vault_id},
                )
                raise
            logger.warning("Vault password update conflict", vault_id=vault_id)
            raise ConflictError("Vault envelopes changed on another device") from e

        logger.info(
            "Vault password envelopes updated",
            **{"vault_id": vault_id, "envelope_version": values[":next"]},
        )
        return {"envelope_version": values[":next"]}

    def mark_deleting(self, user_id: str, vault_id: str) -> None:
        """
        Mark the vault DELETING (spec 4.3, "DeleteVault, first call").

        Idempotent: returns normally when the vault is already DELETING.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Raises:
            NotFoundError: If the vault is missing or unowned
            ConflictError: If a live (non-stale) rotation holds the lock
        """
        key = {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
        now = int(time.time())

        try:
            self.vaults_table.update_item(
                Key=key,
                UpdateExpression=(
                    "SET deletion_state = :deleting, deletion_started_at = :now, updated_at = :now"
                ),
                ConditionExpression=(
                    "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND "
                    "(attribute_not_exists(rotation_state) OR rotation_state = :idle "
                    "OR (rotation_state = :in_progress AND rotation_locked_at < :stale))"
                ),
                ExpressionAttributeValues={
                    ":deleting": "DELETING",
                    ":now": now,
                    ":idle": "IDLE",
                    ":in_progress": "IN_PROGRESS",
                    ":stale": now - STALE_LOCK_SECONDS,
                },
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                logger.error(
                    "Failed to mark vault for deletion",
                    **{"error": str(e), "vault_id": vault_id},
                )
                raise
            item = self._read(key)
            if not item:
                raise NotFoundError("Vault not found") from e
            if item.get("deletion_state") == "DELETING":
                logger.info(
                    "Vault deletion resumed",
                    **{"vault_id": vault_id, "deletion_state": "DELETING"},
                )
                return
            logger.warning("Vault deletion blocked by rotation lock", vault_id=vault_id)
            raise ConflictError(
                "A key rotation is in progress; finish it before deleting this vault"
            ) from e

        logger.info(
            "Vault marked for deletion",
            **{"vault_id": vault_id, "deletion_state": "DELETING"},
        )

    def delete_vault_row(self, user_id: str, vault_id: str) -> None:
        """
        Remove the vault row once every dependent row is gone (spec 4.3, final step).

        Idempotent: returns normally whether this call removed the row or a
        concurrent call already removed it.

        Args:
            user_id: User identifier
            vault_id: Vault identifier
        """
        try:
            self.vaults_table.delete_item(
                Key={"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
                ConditionExpression="deletion_state = :deleting",
                ExpressionAttributeValues={":deleting": "DELETING"},
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.info("Vault row already removed", **{"vault_id": vault_id})
                return
            logger.error(
                "Failed to delete vault row",
                **{"error": str(e), "vault_id": vault_id},
            )
            raise

        logger.info(
            "Vault row deleted",
            **{"vault_id": vault_id, "deletion_state": "DELETED"},
        )

    def update_vault_rotation(
        self,
        user_id: str,
        vault_id: str,
        action: str,
        expected_state: Optional[str] = None,
        expected_envelope_version: Optional[int] = None,
        new_vmk_version: Optional[int] = None,
        wrapped_new_vmk: Optional[bytes] = None,
        new_encrypted_name: Optional[bytes] = None,
    ) -> Dict:
        """
        Drive the vault rotation lock over VMK envelopes with one conditional write.

        ACQUIRE: append {vmk_version, wrapped_vmk, created_at} to vmk_envelopes and
        bump current_vmk_version/envelope_version, then take the lock (-> IN_PROGRESS;
        a lock older than 7 days may be stolen). newVmkVersion must be the current
        version plus one and expectedEnvelopeVersion guards the append. RELEASE:
        -> IDLE only (the versions were already bumped by ACQUIRE), optionally
        storing the re-encrypted name.

        Returns:
            Dictionary with rotation_state, rotation_locked_at,
            current_vmk_version and envelope_version.

        Raises:
            BadRequestError: Unknown action, or ACQUIRE missing its envelope inputs
                or not advancing the VMK version by one.
            NotFoundError: The vault does not exist.
            ConflictError: The condition failed, the vault is being deleted, or a
                live rotation holds the lock.
        """
        key = {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
        now = int(time.time())

        if action == "ACQUIRE":
            update_expr, condition, values = self._acquire_expression(
                key,
                expected_envelope_version,
                new_vmk_version,
                wrapped_new_vmk,
                now,
            )
        elif action == "RELEASE":
            update_expr, condition, values = self._release_expression(
                expected_state, new_encrypted_name, now
            )
        else:
            raise BadRequestError(f"Unknown rotation action: {action}")

        try:
            resp = self.vaults_table.update_item(
                Key=key,
                UpdateExpression=update_expr,
                ConditionExpression=condition,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            self._rotation_conflict(key, vault_id, action, e)

        return self._rotation_result(resp)

    def _rotation_conflict(self, key: dict, vault_id: str, action: str, e: ClientError) -> NoReturn:
        """Raise the right error for a failed rotation condition (never returns)."""
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # Disambiguate the failed condition with one read, as update_vault does.
            item = self._read(key)
            if not item:
                logger.warning(
                    "Vault rotation attempted on missing vault",
                    vault_id=vault_id,
                    action=action,
                )
                raise NotFoundError("Vault not found") from e
            if item.get("deletion_state"):
                logger.warning("Vault rotation blocked, vault is being deleted", vault_id=vault_id)
                raise ConflictError("Vault is being deleted") from e
            logger.warning(
                "Vault rotation conflict",
                **{"vault_id": vault_id, "action": action},
            )
            raise ConflictError(
                "A vault password change is already in progress on another device"
            ) from e
        logger.error(
            "Failed to update vault rotation state",
            **{"error": str(e), "vault_id": vault_id, "action": action},
        )
        raise e

    @staticmethod
    def _rotation_result(resp: dict) -> Dict:
        """Map an ALL_NEW rotation write response to the service return shape."""
        attrs = resp.get("Attributes", {})
        return {
            "rotation_state": attrs.get("rotation_state", "IDLE"),
            "rotation_locked_at": (
                int(attrs["rotation_locked_at"]) if attrs.get("rotation_locked_at") else None
            ),
            "current_vmk_version": int(attrs.get("current_vmk_version", 0)),
            "envelope_version": int(attrs.get("envelope_version", 0)),
        }

    def _acquire_expression(
        self,
        key: dict,
        expected_envelope_version: Optional[int],
        new_vmk_version: Optional[int],
        wrapped_new_vmk: Optional[bytes],
        now: int,
    ) -> tuple[str, str, dict]:
        """Read, validate the next VMK version, and build the guarded ACQUIRE write."""
        if expected_envelope_version is None:
            raise BadRequestError("ACQUIRE requires expectedEnvelopeVersion")
        if new_vmk_version is None or wrapped_new_vmk is None:
            raise BadRequestError("ACQUIRE requires newVmkVersion and wrappedNewVmk")
        if len(wrapped_new_vmk) != WRAPPED_VMK_BYTES:
            raise BadRequestError(f"wrappedNewVmk must be {WRAPPED_VMK_BYTES} bytes")

        item = self._read(key, consistent=True)
        if not item:
            raise NotFoundError("Vault not found")
        if item.get("deletion_state"):
            raise ConflictError("Vault is being deleted")

        current = int(item.get("current_vmk_version", 0))
        if new_vmk_version != current + 1:
            raise BadRequestError("newVmkVersion must be the current version plus one")

        envelopes = _envelope_dicts(item)
        envelopes.append(
            {
                "vmk_version": new_vmk_version,
                "wrapped_vmk": wrapped_new_vmk,
                "created_at": now,
            }
        )

        update_expr = (
            "SET rotation_state = :in_progress, rotation_locked_at = :now, updated_at = :now, "
            "current_vmk_version = :nv, envelope_version = :nev, vmk_envelopes = :env"
        )
        condition = (
            "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND ("
            "attribute_not_exists(rotation_state) OR rotation_state = :idle OR "
            "(rotation_state = :in_progress AND rotation_locked_at < :stale))"
            " AND envelope_version = :expected_env"
        )
        values: dict = {
            ":idle": "IDLE",
            ":in_progress": "IN_PROGRESS",
            ":stale": now - STALE_LOCK_SECONDS,
            ":now": now,
            ":nv": new_vmk_version,
            ":nev": expected_envelope_version + 1,
            ":env": envelopes,
            ":expected_env": expected_envelope_version,
        }
        return update_expr, condition, values

    @staticmethod
    def _release_expression(
        expected_state: Optional[str], new_encrypted_name: Optional[bytes], now: int
    ) -> tuple[str, str, dict]:
        """Build the guarded RELEASE write: flip to IDLE, optionally store the name."""
        if expected_state is None:
            raise BadRequestError("RELEASE requires expectedState")
        update_expr = "SET rotation_state = :idle, updated_at = :now"
        values: dict = {":idle": "IDLE", ":expected": expected_state, ":now": now}
        if new_encrypted_name is not None:
            update_expr += ", encrypted_name = :name"
            values[":name"] = new_encrypted_name
        condition = "attribute_not_exists(deletion_state) AND rotation_state = :expected"
        return update_expr, condition, values
