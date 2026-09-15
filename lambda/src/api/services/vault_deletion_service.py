"""
Vault deletion sweep for Cortex API.

One call does a bounded, idempotent slice of the work (spec section 5): mark
the vault row DELETING, remove item rows with their S3 objects and tag rows,
then collections, then shares, then the vault row itself. The client calls
again until the response says DELETED, or the vault answers 404.
"""

import time
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.api.services.collection_service import CollectionService
from src.api.services.item_service import tag_index_key
from src.api.services.vault_service import VaultService
from src.shared.exceptions import InternalError
from src.shared.logger import get_logger
from src.shared.models import ItemType
from src.shared.repository import DynamoDBRepository, S3Repository

logger = get_logger("vault_deletion_service")

ITEM_BATCH = 25
BUDGET_SECONDS = 20
SHARES_PAGE = 100


@dataclass
class _Run:
    """One call's wall-clock start and the counters reported back."""

    user_id: str
    vault_id: str
    started: float
    deleted_items: int = 0
    deleted_collections: int = 0
    deleted_shares: int = 0
    skipped: int = 0

    def budget_spent(self) -> bool:
        return time.monotonic() - self.started >= BUDGET_SECONDS

    def owns(self, row: dict) -> bool:
        """Per-row guard: skip and count any row keyed under another vault."""
        if row.get("vault_id") == self.vault_id:
            return True
        self.skipped += 1
        return False


class VaultDeletionService:
    """Bounded, resumable deletion of a vault and everything stored under it."""

    def __init__(
        self,
        session: boto3.Session,
        vault_service: VaultService,
        collection_service: CollectionService,
        items_table_name: str,
        shares_table_name: str,
        s3_bucket_name: str,
    ):
        self.vault_service = vault_service
        self.collection_service = collection_service
        self.items_repo = DynamoDBRepository(session, items_table_name)
        self.shares_repo = DynamoDBRepository(session, shares_table_name)
        self.s3_repo = S3Repository(session, s3_bucket_name)

    def delete_vault(self, user_id: str, vault_id: str) -> dict:
        """
        Run one bounded deletion step for the caller's vault.

        Returns:
            deletion_state ("DELETING" while work remains, "DELETED" once the
            vault row is gone) plus the rows removed by this call.

        Raises:
            NotFoundError: unknown, unowned, or already deleted vault
            ConflictError: a live rotation lock holds the vault
            InternalError: an S3 delete failed; the item row is kept for retry
        """
        run = _Run(user_id=user_id, vault_id=vault_id, started=time.monotonic())
        self.vault_service.mark_deleting(user_id, vault_id)

        finished = (
            self._sweep_items(run) and self._sweep_collections(run) and self._sweep_shares(run)
        )
        if finished:
            self.vault_service.delete_vault_row(user_id, vault_id)
        state = "DELETED" if finished else "DELETING"

        if run.skipped:
            logger.warning(
                "Skipped rows keyed under another vault", vault_id=vault_id, skipped=run.skipped
            )
        logger.info(
            "Vault deletion step finished",
            vault_id=vault_id,
            deletion_state=state,
            deleted_items=run.deleted_items,
            deleted_collections=run.deleted_collections,
            deleted_shares=run.deleted_shares,
        )
        return {
            "deletion_state": state,
            "deleted_items": run.deleted_items,
            "deleted_collections": run.deleted_collections,
            "deleted_shares": run.deleted_shares,
        }

    def _sweep_items(self, run: _Run) -> bool:
        """Step 1: GSI2 pages of item rows; True once a page comes back empty."""
        start_key: dict[str, Any] | None = None
        while True:
            if run.budget_spent():
                return False
            page = self.items_repo.query(
                key_condition_expression="GSI2PK = :pk",
                expression_attribute_values={":pk": f"VAULT#{run.vault_id}"},
                index_name="GSI2",
                limit=ITEM_BATCH,
                exclusive_start_key=start_key,
            )
            if not page["Items"]:
                return True
            items = [row for row in page["Items"] if run.owns(row)]
            if not items and not page.get("LastEvaluatedKey"):
                return True
            for item in items:
                self._delete_media_object(run.vault_id, item)
            if items:
                with self.items_repo.table.batch_writer() as writer:
                    for item in items:
                        writer.delete_item(Key={"PK": f"ITEM#{item['item_id']}", "SK": "METADATA"})
                        for tag in item.get("encrypted_tags") or []:
                            writer.delete_item(
                                Key=tag_index_key(run.vault_id, item["item_id"], tag)
                            )
                run.deleted_items += len(items)
            start_key = page.get("LastEvaluatedKey")

    def _delete_media_object(self, vault_id: str, item: dict) -> None:
        """S3 before DynamoDB: abort a pending multipart upload, then delete the object."""
        s3_key = item.get("s3_key")
        if item.get("item_type") != ItemType.MEDIA or not s3_key:
            return
        try:
            if item.get("upload_status") == "PENDING" and item.get("upload_id"):
                self._abort_upload(s3_key, item["upload_id"])
            self.s3_repo.delete_object(s3_key)
        except ClientError as e:
            logger.error(
                "S3 cleanup failed during vault deletion",
                vault_id=vault_id,
                item_id=item.get("item_id"),
                error_code=e.response.get("Error", {}).get("Code"),
            )
            raise InternalError("Failed to delete vault media") from e

    def _abort_upload(self, s3_key: str, upload_id: str) -> None:
        try:
            self.s3_repo.abort_multipart_upload(s3_key, upload_id)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "NoSuchUpload":
                raise

    def _sweep_collections(self, run: _Run) -> bool:
        """Step 2: purge each collection on a page; True once a page comes back empty."""
        repo = self.collection_service.collections_repo
        start_key: dict[str, Any] | None = None
        while True:
            if run.budget_spent():
                return False
            page = repo.query(
                key_condition_expression="PK = :pk AND begins_with(SK, :sk_prefix)",
                expression_attribute_values={
                    ":pk": f"VAULT#{run.vault_id}",
                    ":sk_prefix": "COLLECTION#",
                },
                limit=ITEM_BATCH,
                exclusive_start_key=start_key,
            )
            if not page["Items"]:
                return True
            owned = [row for row in page["Items"] if run.owns(row)]
            if not owned and not page.get("LastEvaluatedKey"):
                return True
            for row in owned:
                if not self.collection_service.purge_collection(
                    run.vault_id, row["collection_id"], run.budget_spent
                ):
                    return False
                run.deleted_collections += 1
            start_key = page.get("LastEvaluatedKey")

    def _sweep_shares(self, run: _Run) -> bool:
        """Step 3: filtered scan; ends only when a page carries no LastEvaluatedKey."""
        start_key: dict[str, Any] | None = None
        while True:
            if run.budget_spent():
                return False
            page = self.shares_repo.scan(
                filter_expression="vault_id = :v AND user_id = :u",
                expression_attribute_values={":v": run.vault_id, ":u": run.user_id},
                limit=SHARES_PAGE,
                exclusive_start_key=start_key,
            )
            rows = [row for row in page["Items"] if run.owns(row)]
            if rows:
                with self.shares_repo.table.batch_writer() as writer:
                    for row in rows:
                        writer.delete_item(Key={"PK": row["PK"], "SK": row["SK"]})
                run.deleted_shares += len(rows)
            start_key = page.get("LastEvaluatedKey")
            if not start_key:
                return True
