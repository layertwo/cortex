"""
Property-Based Tests for Vault Deletion.

Feature: cortex, Property 4: Vault data isolation
Feature: cortex, Property 8: Deletion maintains referential integrity

Property 4: a full deletion run of vault A never touches a row of vault B.
The fixture pages interleave vault B rows (a mis-keyed item, collection and
share) with vault A rows; every DeleteRequest key and every S3 key is pinned
in expected_params to vault A, so a vault B key reaching DynamoDB or S3 is a
Stubber assertion failure.

Property 8: S3 before DynamoDB. The S3 and DynamoDB Stubbers are independent
queues, so ordering is proven by the failure case: the S3 delete fails and no
batch_write_item is stubbed; the service must raise before any row delete.
A reversed implementation trips an unstubbed DynamoDB request.
"""

import pytest

from src.shared.exceptions import InternalError
from tests.fixtures.vault_deletion import (
    ITEMS_TABLE,
    SHARES_TABLE,
    collection_row,
    item_key,
    media_row,
    note_row,
    s3_key_for,
    share_key,
    share_row,
    stub_batch_delete,
    stub_collections_page,
    stub_items_page,
    stub_mark,
    stub_purge,
    stub_row_delete,
    stub_s3_delete,
    stub_shares_page,
    tag_key,
)

USER = "user-owner"
VAULT_A = "vault-a"
VAULT_B = "vault-b"
TAG = b"tag-a"


class TestVaultDeletionIsolation:
    """Property 4: every key the sweep deletes belongs to the vault being deleted."""

    def test_full_run_touches_only_vault_a_keys(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT_A)

        # Items page: A media, B media (mis-keyed), A note with a tag.
        stub_items_page(
            dynamodb_stubber,
            VAULT_A,
            [
                media_row("a-media", VAULT_A, USER),
                media_row("b-media", VAULT_B, USER),
                note_row("a-note", VAULT_A, USER, tags=(TAG,)),
            ],
        )
        stub_s3_delete(s3_stubber, s3_key_for(VAULT_A, "a-media"))
        stub_batch_delete(
            dynamodb_stubber,
            ITEMS_TABLE,
            [item_key("a-media"), item_key("a-note"), tag_key(VAULT_A, "a-note", TAG)],
        )
        stub_items_page(dynamodb_stubber, VAULT_A, [])

        # Collections page: B collection first, then A collection.
        stub_collections_page(
            dynamodb_stubber,
            VAULT_A,
            [collection_row("b-col", VAULT_B, USER), collection_row("a-col", VAULT_A, USER)],
        )
        stub_purge(dynamodb_stubber, VAULT_A, "a-col", ["a-note"], USER)
        stub_collections_page(dynamodb_stubber, VAULT_A, [])

        # Shares page: A share and B share.
        stub_shares_page(
            dynamodb_stubber,
            USER,
            VAULT_A,
            [share_row("a-share", VAULT_A, USER), share_row("b-share", VAULT_B, USER)],
        )
        stub_batch_delete(dynamodb_stubber, SHARES_TABLE, [share_key("a-share")])
        stub_row_delete(dynamodb_stubber, USER, VAULT_A)

        result = vault_deletion_service.delete_vault(USER, VAULT_A)

        assert result == {
            "deletion_state": "DELETED",
            "deleted_items": 2,
            "deleted_collections": 1,
            "deleted_shares": 1,
        }

    def test_positive_control_vault_b_row_is_deleted_when_b_is_the_target(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        # Non-vacuity: the same B row IS deleted when B is the vault being deleted,
        # proving the skips above come from the per-row guard.
        stub_mark(dynamodb_stubber, USER, VAULT_B)
        stub_items_page(dynamodb_stubber, VAULT_B, [media_row("b-media", VAULT_B, USER)])
        stub_s3_delete(s3_stubber, s3_key_for(VAULT_B, "b-media"))
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, [item_key("b-media")])
        stub_items_page(dynamodb_stubber, VAULT_B, [])
        stub_collections_page(dynamodb_stubber, VAULT_B, [])
        stub_shares_page(dynamodb_stubber, USER, VAULT_B, [])
        stub_row_delete(dynamodb_stubber, USER, VAULT_B)

        assert vault_deletion_service.delete_vault(USER, VAULT_B)["deleted_items"] == 1


class TestDeletionOrdering:
    """Property 8: the S3 object goes before the DynamoDB row, never after."""

    def test_s3_failure_stops_the_sweep_before_any_row_delete(
        self, vault_deletion_service, dynamodb_stubber, s3_stubber
    ):
        stub_mark(dynamodb_stubber, USER, VAULT_A)
        stub_items_page(dynamodb_stubber, VAULT_A, [media_row("a-media", VAULT_A, USER)])
        s3_stubber.add_client_error(
            "delete_object",
            service_error_code="InternalError",
            service_message="We encountered an internal error",
            http_status_code=500,
        )

        with pytest.raises(InternalError):
            vault_deletion_service.delete_vault(USER, VAULT_A)

        dynamodb_stubber.assert_no_pending_responses()
        s3_stubber.assert_no_pending_responses()
