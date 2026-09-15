"""
Rotation abandon safety check for Cortex API.

ABANDON discards a staged rotation pair (pending_vault_salt, pending_verifier)
so a user who forgot the new password can retry with the old one. That is
only safe when nothing was already wrapped under the staged keys, so this
service pages the vault's items (GSI2) and collections (the vault partition)
for any row whose version exceeds the vault's current KEK version before
calling VaultService.abandon_rotation to perform the write (spec section 3).

Composition mirrors VaultDeletionService: a DynamoDBRepository built directly
for the item check, collection_service.collections_repo for the collection
check, and the same per-row vault_id guard as the deletion sweep.
"""

import time

import boto3

from src.api.services.collection_service import CollectionService
from src.api.services.vault_service import STALE_LOCK_SECONDS, VaultService
from src.shared.exceptions import ConflictError
from src.shared.logger import get_logger
from src.shared.repository import DynamoDBRepository

logger = get_logger("rotation_abandon_service")

PAGE_LIMIT = 100
REKEYED_MESSAGE = (
    "Some files were already re-keyed; finish the password change with the new password"
)
CONFLICT_MESSAGE = "A vault password change is already in progress on another device"


class RotationAbandonService:
    """Verifies no row was re-keyed under a staged rotation, then discards it."""

    def __init__(
        self,
        session: boto3.Session,
        vault_service: VaultService,
        collection_service: CollectionService,
        items_table_name: str,
    ):
        self.vault_service = vault_service
        self.collection_service = collection_service
        self.items_repo = DynamoDBRepository(session, items_table_name)

    def abandon(self, user_id: str, vault_id: str) -> dict:
        """
        Discard the vault's staged rotation pair once no row is re-keyed under it.

        Returns:
            {"rotation_state": "IDLE", "rotation_locked_at": None,
             "pending_vault_salt": None, "pending_verifier": None}

        Raises:
            NotFoundError: unknown, unowned, or DELETING vault (from get_vault)
            ConflictError: the vault is not PAUSED or a stale IN_PROGRESS lock
                (pre-flight, before any scan), a row was already wrapped
                under the staged keys, or the vault row fails
                abandon_rotation's write condition
        """
        vault = self.vault_service.get_vault(user_id, vault_id)
        kek_version = vault["kek_version"]
        state = vault["rotation_state"]
        locked_at = vault["rotation_locked_at"]

        if state != "PAUSED" and not (
            state == "IN_PROGRESS"
            and locked_at is not None
            and locked_at < int(time.time()) - STALE_LOCK_SECONDS
        ):
            raise ConflictError(CONFLICT_MESSAGE)

        self._check_rows(
            self.items_repo,
            {
                "index_name": "GSI2",
                "key_condition_expression": "GSI2PK = :pk",
                "filter_expression": "dek_version > :kek",
                "expression_attribute_values": {":pk": f"VAULT#{vault_id}", ":kek": kek_version},
            },
            vault_id,
            "an item",
        )
        self._check_rows(
            self.collection_service.collections_repo,
            {
                "key_condition_expression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "filter_expression": "metadata_version > :kek",
                "expression_attribute_values": {
                    ":pk": f"VAULT#{vault_id}",
                    ":sk_prefix": "COLLECTION#",
                    ":kek": kek_version,
                },
            },
            vault_id,
            "a collection",
        )

        logger.info(
            "Rotation abandon check finished",
            vault_id=vault_id,
            action="ABANDON",
            rekeyed_items=0,
            rekeyed_collections=0,
        )
        return self.vault_service.abandon_rotation(user_id, vault_id, expected_locked_at=locked_at)

    def _check_rows(self, repo, query_kwargs: dict, vault_id: str, what: str) -> None:
        """Page repo.query(**query_kwargs) to exhaustion; raise on the first row this vault owns."""
        start_key: dict | None = None
        while True:
            page = repo.query(limit=PAGE_LIMIT, exclusive_start_key=start_key, **query_kwargs)
            for row in page["Items"]:
                if row.get("vault_id") == vault_id:
                    logger.warning(
                        f"Rotation abandon blocked, {what} is already re-keyed",
                        vault_id=vault_id,
                        action="ABANDON",
                    )
                    raise ConflictError(REKEYED_MESSAGE)
            start_key = page.get("LastEvaluatedKey")
            if not start_key:
                return
