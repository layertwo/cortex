"""
Vault service layer for Cortex API.

This module implements business logic for vault management including
vault creation with salt generation, vault reads and listing, vault name
and verifier updates, deletion marks, and the rotation lock state machine.

Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5
"""

import secrets
import time
import uuid
from typing import Any, Dict, Optional

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


def _vault_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """Map a vault row to the fields shared by get_vault and list_user_vaults."""
    return {
        "vault_id": item["vault_id"],
        "vault_salt": to_bytes(item.get("vault_salt")),
        "encrypted_name": to_bytes(item.get("encrypted_name")),
        "verifier": to_bytes(item.get("verifier")),
        "created_at": int(item["created_at"]),
        "updated_at": int(item.get("updated_at", item["created_at"])),
        "kek_version": int(item["kek_version"]) if item.get("kek_version") is not None else 1,
        "rotation_state": item.get("rotation_state", "IDLE"),
    }


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
        Retrieve the vault record, including rotation state and any staged rotation pair.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Returns:
            Dictionary with vault_id, vault_salt, encrypted_name, verifier,
            pending_vault_salt, pending_verifier, created_at, updated_at,
            kek_version, rotation_state, and rotation_locked_at.

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
        vault["pending_vault_salt"] = to_bytes(item.get("pending_vault_salt"))
        vault["pending_verifier"] = to_bytes(item.get("pending_verifier"))
        vault["rotation_locked_at"] = (
            int(item["rotation_locked_at"]) if item.get("rotation_locked_at") is not None else None
        )
        return vault

    def update_vault(
        self,
        user_id: str,
        vault_id: str,
        encrypted_name: Optional[bytes] = None,
        verifier: Optional[bytes] = None,
    ) -> Dict:
        """
        Store the encrypted vault name and/or the password verifier.

        Args:
            user_id: User identifier
            vault_id: Vault identifier
            encrypted_name: Vault name encrypted under the vault metadata key
            verifier: Password verifier ciphertext

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
        if verifier is not None:
            update_expr += ", verifier = :ver"
            values[":ver"] = verifier

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
                    "(attribute_not_exists(rotation_state) OR rotation_state IN (:idle, :paused) "
                    "OR (rotation_state = :in_progress AND rotation_locked_at < :stale))"
                ),
                ExpressionAttributeValues={
                    ":deleting": "DELETING",
                    ":now": now,
                    ":idle": "IDLE",
                    ":paused": "PAUSED",
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
                "A vault password change is in progress; wait for it to finish or pause it first"
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
        expected_state: str,
        kek_version: Optional[int] = None,
        new_verifier: Optional[bytes] = None,
        new_vault_salt: Optional[bytes] = None,
        new_encrypted_name: Optional[bytes] = None,
    ) -> Dict:
        """
        Drive the vault password rotation state machine with one conditional write.

        ACQUIRE: -> IN_PROGRESS (steals a lock older than 7 days). When
        new_vault_salt and new_verifier are both given they are staged as a
        pair unless a pair is already staged; the staged pair is returned.
        PAUSE: IN_PROGRESS -> PAUSED, keeping the staged pair.
        RELEASE: -> IDLE after a consistent read; validates kek_version
        against the row and promotes the staged pair (or writes new_verifier
        when nothing is staged) in the same guarded write.

        Returns:
            Dictionary with rotation_state, rotation_locked_at,
            pending_vault_salt and pending_verifier (bytes or None).

        Raises:
            BadRequestError: Invalid argument combination for the action.
            NotFoundError: RELEASE on a vault that does not exist.
            ConflictError: The condition failed, or RELEASE conflicts with
                the staged pair or the stored kek_version.
        """
        key = {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
        now = int(time.time())

        if action == "ACQUIRE":
            update_expr, condition, values = self._acquire_expression(
                expected_state, now, new_vault_salt, new_verifier
            )
        elif action == "PAUSE":
            if expected_state != "IN_PROGRESS":
                raise BadRequestError("PAUSE requires expectedState IN_PROGRESS")
            update_expr = "SET rotation_state = :paused, updated_at = :now"
            condition = "attribute_not_exists(deletion_state) AND rotation_state = :expected"
            values = {":paused": "PAUSED", ":expected": expected_state, ":now": now}
        else:
            update_expr, condition, values = self._prepare_release(
                key,
                expected_state,
                now,
                kek_version,
                new_verifier,
                new_vault_salt,
                new_encrypted_name,
            )

        try:
            resp = self.vaults_table.update_item(
                Key=key,
                UpdateExpression=update_expr,
                ConditionExpression=condition,
                ExpressionAttributeValues=values,
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
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
                    logger.warning(
                        "Vault rotation blocked, vault is being deleted", vault_id=vault_id
                    )
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
            raise

        attrs = resp.get("Attributes", {})
        return {
            "rotation_state": attrs.get("rotation_state", "IDLE"),
            "rotation_locked_at": (
                int(attrs["rotation_locked_at"]) if attrs.get("rotation_locked_at") else None
            ),
            "pending_vault_salt": to_bytes(attrs.get("pending_vault_salt")),
            "pending_verifier": to_bytes(attrs.get("pending_verifier")),
        }

    @staticmethod
    def _acquire_expression(
        expected_state: str,
        now: int,
        new_vault_salt: Optional[bytes],
        new_verifier: Optional[bytes],
    ) -> tuple[str, str, dict]:
        """Build the ACQUIRE write; stages the salt/verifier pair only if none is staged."""
        if (new_vault_salt is None) != (new_verifier is None):
            raise BadRequestError("newVaultSalt and newVerifier must be supplied together")
        if new_vault_salt is not None and len(new_vault_salt) != 16:
            raise BadRequestError("Vault salt must be exactly 16 bytes")

        update_expr = (
            "SET rotation_state = :in_progress, rotation_locked_at = :now, updated_at = :now"
        )
        condition = (
            "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND ("
            "attribute_not_exists(rotation_state) OR rotation_state = :expected OR "
            "(rotation_state = :in_progress AND rotation_locked_at < :stale))"
        )
        values: dict = {
            ":in_progress": "IN_PROGRESS",
            ":expected": expected_state,
            ":stale": now - STALE_LOCK_SECONDS,
            ":now": now,
        }
        if new_vault_salt is not None:
            update_expr += (
                ", pending_vault_salt = if_not_exists(pending_vault_salt, :salt)"
                ", pending_verifier = if_not_exists(pending_verifier, :pv)"
            )
            values[":salt"] = new_vault_salt
            values[":pv"] = new_verifier
        return update_expr, condition, values

    def _prepare_release(
        self,
        key: dict,
        expected_state: str,
        now: int,
        kek_version: Optional[int],
        new_verifier: Optional[bytes],
        new_vault_salt: Optional[bytes],
        new_encrypted_name: Optional[bytes],
    ) -> tuple[str, str, dict]:
        """Read the row, validate the request against it, and build the guarded RELEASE write."""
        if new_vault_salt is not None:
            raise BadRequestError("newVaultSalt is staged on ACQUIRE and not accepted on RELEASE")

        item = self._read(key, consistent=True)
        if not item:
            raise NotFoundError("Vault not found")
        pending_salt = item.get("pending_vault_salt")
        pending_verifier = item.get("pending_verifier")
        staged = pending_salt is not None
        current_kek = int(item.get("kek_version", 1))

        if staged and (kek_version is None or new_verifier is not None):
            raise ConflictError(
                "A rotation with a new salt is staged; commit it with kekVersion only, or PAUSE"
            )
        if kek_version is not None and kek_version != current_kek + 1:
            raise ConflictError("kekVersion must be the current version plus one")

        update_expr = "SET rotation_state = :idle, updated_at = :now"
        condition = "attribute_not_exists(deletion_state) AND rotation_state = :expected"
        values: dict = {":idle": "IDLE", ":expected": expected_state, ":now": now}
        if kek_version is not None:
            update_expr += ", kek_version = :kv"
            values[":kv"] = kek_version
        if new_encrypted_name is not None:
            update_expr += ", encrypted_name = :name"
            values[":name"] = new_encrypted_name
        if staged:
            update_expr += (
                ", vault_salt = :pending_salt, verifier = :pending_verifier"
                " REMOVE pending_vault_salt, pending_verifier"
            )
            values[":pending_salt"] = pending_salt
            values[":pending_verifier"] = pending_verifier
            condition += (
                " AND pending_vault_salt = :pending_salt AND pending_verifier = :pending_verifier"
            )
        else:
            if new_verifier is not None:
                update_expr += ", verifier = :ver"
                values[":ver"] = new_verifier
            condition += " AND attribute_not_exists(pending_vault_salt)"
        if kek_version is not None:
            if "kek_version" in item:
                condition += " AND kek_version = :prev"
                values[":prev"] = current_kek
            else:
                condition += " AND attribute_not_exists(kek_version)"
        return update_expr, condition, values
