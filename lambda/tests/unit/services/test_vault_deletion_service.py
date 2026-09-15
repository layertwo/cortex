"""
Unit tests for VaultDeletionService (spec section 5).

Each phase of the sweep is its own test with the exact Stubber sequence the
service must issue: update_item (mark) -> query GSI2 pages -> S3 deletes ->
batch_write_item -> query collections -> purge -> scan shares -> batch_write_item
-> delete_item (vault row). Unstubbed calls fail the test, so a passing test
also proves nothing else was touched.
"""

import time

import pytest

from src.shared.exceptions import ConflictError, InternalError, NotFoundError
from tests.fixtures.vault_deletion import (
    COLLECTIONS_TABLE,
    ITEMS_TABLE,
    MEMBERSHIPS_KEY_CONDITION,
    SHARES_TABLE,
    collection_row,
    item_key,
    media_row,
    membership_key,
    membership_row,
    note_row,
    s3_key_for,
    share_key,
    share_row,
    stub_batch_delete,
    stub_collections_page,
    stub_empty_tail,
    stub_items_page,
    stub_mark,
    stub_mark_condition_failed,
    stub_purge,
    stub_row_delete,
    stub_s3_abort,
    stub_s3_delete,
    stub_shares_page,
    tag_key,
    vault_row,
    wire,
)

USER = "user-a"
VAULT = "vault-a"


class TestMarkStep:
    def test_live_rotation_lock_raises_conflict_and_does_no_work(
        self, vault_deletion_service, dynamodb_stubber
    ):
        locked = vault_row(
            USER,
            VAULT,
            rotation_state={"S": "IN_PROGRESS"},
            rotation_locked_at={"N": str(int(time.time()))},
        )
        stub_mark_condition_failed(dynamodb_stubber, USER, VAULT, locked)

        with pytest.raises(ConflictError, match="wait for it to finish or pause it first"):
            vault_deletion_service.delete_vault(USER, VAULT)

    def test_missing_vault_raises_not_found(self, vault_deletion_service, dynamodb_stubber):
        stub_mark_condition_failed(dynamodb_stubber, USER, VAULT, None)

        with pytest.raises(NotFoundError, match="Vault not found"):
            vault_deletion_service.delete_vault(USER, VAULT)

    def test_retry_on_deleting_vault_proceeds_to_the_sweep(
        self, vault_deletion_service, dynamodb_stubber
    ):
        already = vault_row(USER, VAULT, deletion_state={"S": "DELETING"})
        stub_mark_condition_failed(dynamodb_stubber, USER, VAULT, already)
        stub_empty_tail(dynamodb_stubber, USER, VAULT)
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result == {
            "deletion_state": "DELETED",
            "deleted_items": 0,
            "deleted_collections": 0,
            "deleted_shares": 0,
        }


class TestItemsPhase:
    def test_items_page_deletes_s3_objects_then_item_and_tag_rows(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        tag = b"tag-1"
        rows = [
            media_row("m1", VAULT, USER, tags=(tag,)),
            media_row("m2", VAULT, USER, upload_status="PENDING", upload_id="up-2"),
            note_row("n1", VAULT, USER, tags=(tag, b"tag-2")),
        ]
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, rows)
        stub_s3_delete(s3_stubber, s3_key_for(VAULT, "m1"))
        stub_s3_abort(s3_stubber, s3_key_for(VAULT, "m2"), "up-2")
        stub_s3_delete(s3_stubber, s3_key_for(VAULT, "m2"))
        stub_batch_delete(
            dynamodb_stubber,
            ITEMS_TABLE,
            [
                item_key("m1"),
                tag_key(VAULT, "m1", tag),
                item_key("m2"),
                item_key("n1"),
                tag_key(VAULT, "n1", tag),
                tag_key(VAULT, "n1", b"tag-2"),
            ],
        )
        stub_empty_tail(dynamodb_stubber, USER, VAULT)
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deletion_state"] == "DELETED"
        assert result["deleted_items"] == 3

    def test_items_follow_last_evaluated_key_and_flush_every_25(
        self, vault_deletion_service, dynamodb_stubber
    ):
        ids = [f"n{i:02d}" for i in range(25)]
        rows = [note_row(i, VAULT, USER, tags=(b"t",)) for i in ids]
        keys = [k for i in ids for k in (item_key(i), tag_key(VAULT, i, b"t"))]
        last = {"PK": f"ITEM#{ids[-1]}", "SK": "METADATA", "GSI2PK": f"VAULT#{VAULT}"}

        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, rows, last_key=wire(last))
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, keys[:25])
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, keys[25:])
        stub_items_page(dynamodb_stubber, VAULT, [], start_key=last)
        stub_empty_tail(dynamodb_stubber, USER, VAULT, from_step=2)
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deleted_items"] == 25
        assert result["deletion_state"] == "DELETED"

    def test_no_such_upload_on_abort_is_ignored(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        key = s3_key_for(VAULT, "m1")
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(
            dynamodb_stubber,
            VAULT,
            [media_row("m1", VAULT, USER, upload_status="PENDING", upload_id="gone")],
        )
        s3_stubber.add_client_error(
            "abort_multipart_upload",
            service_error_code="NoSuchUpload",
            service_message="The specified upload does not exist",
            http_status_code=404,
        )
        stub_s3_delete(s3_stubber, key)
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, [item_key("m1")])
        stub_empty_tail(dynamodb_stubber, USER, VAULT)
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        assert vault_deletion_service.delete_vault(USER, VAULT)["deleted_items"] == 1

    def test_s3_failure_raises_internal_error_and_keeps_the_row(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [media_row("m1", VAULT, USER)])
        s3_stubber.add_client_error(
            "delete_object",
            service_error_code="InternalError",
            service_message="We encountered an internal error",
            http_status_code=500,
        )
        # No batch_write_item and no vault-row delete are stubbed: any row
        # delete after the S3 failure would be an unstubbed call.

        with pytest.raises(InternalError, match="Failed to delete vault media"):
            vault_deletion_service.delete_vault(USER, VAULT)

    def test_foreign_vault_rows_are_skipped_and_not_counted(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(
            dynamodb_stubber,
            VAULT,
            [media_row("mine", VAULT, USER), media_row("theirs", "vault-b", USER)],
        )
        stub_s3_delete(s3_stubber, s3_key_for(VAULT, "mine"))
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, [item_key("mine")])
        stub_empty_tail(dynamodb_stubber, USER, VAULT)
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deleted_items"] == 1

    def test_items_page_of_only_foreign_rows_terminates_the_sweep(
        self, vault_deletion_service, dynamodb_stubber
    ):
        """A page with no owned rows and no cursor ends step 1 without cycling back."""
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [media_row("theirs", "vault-b", USER)])
        # Next stub is step 2's first call: if step 1 cycled instead of
        # terminating, this query's params would not match and the test fails.
        stub_empty_tail(dynamodb_stubber, USER, VAULT, from_step=2)
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deleted_items"] == 0
        assert result["deletion_state"] == "DELETED"


class TestBudget:
    def test_budget_spent_after_items_page_returns_deleting(
        self, vault_deletion_service, dynamodb_stubber, monkeypatch
    ):
        # monotonic() is read once at the start of the call, then once before
        # every page: 0.0 (start), 0.0 (items page 1), 20.0 (items page 2 -> stop).
        ticks = iter([0.0, 0.0, 20.0])
        monkeypatch.setattr(time, "monotonic", lambda: next(ticks, 20.0))

        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [note_row("n1", VAULT, USER)])
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, [item_key("n1")])
        # Nothing else stubbed: a collection query, scan, or vault-row delete
        # would be an unstubbed call and fail the test.

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result == {
            "deletion_state": "DELETING",
            "deleted_items": 1,
            "deleted_collections": 0,
            "deleted_shares": 0,
        }


class TestCollectionsPhase:
    def test_collections_page_purges_each_collection(
        self, vault_deletion_service, dynamodb_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [])
        stub_collections_page(
            dynamodb_stubber,
            VAULT,
            [collection_row("c1", VAULT, USER), collection_row("c2", VAULT, USER)],
        )
        stub_purge(dynamodb_stubber, VAULT, "c1", ["i1", "i2"], USER)
        stub_purge(dynamodb_stubber, VAULT, "c2", [], USER)
        stub_collections_page(dynamodb_stubber, VAULT, [])
        stub_shares_page(dynamodb_stubber, USER, VAULT, [])
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deleted_collections"] == 2
        assert result["deletion_state"] == "DELETED"

    def test_foreign_collection_row_is_skipped(self, vault_deletion_service, dynamodb_stubber):
        """A page with no owned rows and no cursor ends step 2 without cycling back."""
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [])
        stub_collections_page(dynamodb_stubber, VAULT, [collection_row("cb", "vault-b", USER)])
        # Next stub is step 3's first call: if step 2 cycled instead of
        # terminating, this scan's params would not match and the test fails.
        stub_shares_page(dynamodb_stubber, USER, VAULT, [])
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        assert vault_deletion_service.delete_vault(USER, VAULT)["deleted_collections"] == 0

    def test_budget_trips_inside_a_purge_returns_deleting(
        self, vault_deletion_service, dynamodb_stubber, monkeypatch
    ):
        """A budget that trips between a purge's membership pages stops before the row delete."""
        ticks = iter([0.0, 0.0, 0.0, 20.0])
        monkeypatch.setattr(time, "monotonic", lambda: next(ticks, 20.0))

        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [])
        stub_collections_page(dynamodb_stubber, VAULT, [collection_row("c1", VAULT, USER)])
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [membership_row("c1", "i1", VAULT, USER)],
                "LastEvaluatedKey": wire({"PK": "COLLECTION#c1", "SK": "ITEM#i1"}),
            },
            {
                "TableName": COLLECTIONS_TABLE,
                "KeyConditionExpression": MEMBERSHIPS_KEY_CONDITION,
                "ExpressionAttributeValues": {":pk": "COLLECTION#c1"},
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )
        stub_batch_delete(dynamodb_stubber, COLLECTIONS_TABLE, [membership_key("c1", "i1")])
        # No further query, and no delete_item, is stubbed: the collection row
        # and the vault row must both stay undeleted.

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deletion_state"] == "DELETING"
        assert result["deleted_collections"] == 0


class TestSharesPhase:
    def test_shares_scan_then_batch_delete_then_vault_row(
        self, vault_deletion_service, dynamodb_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [])
        stub_collections_page(dynamodb_stubber, VAULT, [])
        stub_shares_page(
            dynamodb_stubber,
            USER,
            VAULT,
            [share_row("s1", VAULT, USER), share_row("s2", VAULT, USER)],
        )
        stub_batch_delete(dynamodb_stubber, SHARES_TABLE, [share_key("s1"), share_key("s2")])
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deleted_shares"] == 2
        assert result["deletion_state"] == "DELETED"

    def test_empty_filtered_page_with_last_key_continues_before_row_delete(
        self, vault_deletion_service, dynamodb_stubber
    ):
        cursor = {"PK": "SHARE#elsewhere", "SK": "METADATA"}
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [])
        stub_collections_page(dynamodb_stubber, VAULT, [])
        stub_shares_page(dynamodb_stubber, USER, VAULT, [], last_key=wire(cursor))
        stub_shares_page(
            dynamodb_stubber, USER, VAULT, [share_row("s1", VAULT, USER)], start_key=cursor
        )
        stub_batch_delete(dynamodb_stubber, SHARES_TABLE, [share_key("s1")])
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        result = vault_deletion_service.delete_vault(USER, VAULT)

        assert result["deleted_shares"] == 1
        assert result["deletion_state"] == "DELETED"

    def test_foreign_share_row_is_skipped(self, vault_deletion_service, dynamodb_stubber):
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_items_page(dynamodb_stubber, VAULT, [])
        stub_collections_page(dynamodb_stubber, VAULT, [])
        stub_shares_page(dynamodb_stubber, USER, VAULT, [share_row("sb", "vault-b", USER)])
        stub_row_delete(dynamodb_stubber, USER, VAULT)

        assert vault_deletion_service.delete_vault(USER, VAULT)["deleted_shares"] == 0


class TestFinalStep:
    def test_concurrent_row_delete_still_reports_deleted(
        self, vault_deletion_service, dynamodb_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT)
        stub_empty_tail(dynamodb_stubber, USER, VAULT)
        dynamodb_stubber.add_client_error(
            "delete_item", service_error_code="ConditionalCheckFailedException"
        )

        assert vault_deletion_service.delete_vault(USER, VAULT)["deletion_state"] == "DELETED"
