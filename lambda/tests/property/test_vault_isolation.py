"""
Property-Based Tests for Vault Data Isolation (Property 4).

Feature: cortex, Property 4: Vault data isolation

For any two distinct users, a user must not be able to read, modify, or delete
another user's item through ANY ItemService operation.

Validates: Requirements 2.4, 3.3, 4.3, 5.1

These exercise the REAL ItemService against botocore-stubbed AWS, so they fail if
an operation forgets its ownership check. Only the initial get_item is stubbed:
any S3 or further DynamoDB call an attacker could trigger would be an unstubbed
request and fail the test — so a passing test proves the denial has NO side
effects (no download URL minted, no object deleted, no multipart assembled).
"""

import pytest
from botocore.stub import ANY

from src.shared.exceptions import NotFoundError
from src.shared.generated.models import (
    AbortItemUploadRequestContent,
    CompleteItemUploadRequestContent,
    CreateUploadPartUrlsRequestContent,
    UploadPart,
)
from src.shared.models import ItemType

OWNER = "user-owner"
ATTACKER = "user-attacker"
ITEM_ID = "item-owned-by-someone-else"
TABLE = "test-items-table"


def _owner_item(user_id=OWNER):
    """A complete MEDIA item owned by `user_id`, in DynamoDB get_item wire form."""
    return {
        "Item": {
            "PK": {"S": f"ITEM#{ITEM_ID}"},
            "SK": {"S": "METADATA"},
            "item_id": {"S": ITEM_ID},
            "item_type": {"S": ItemType.MEDIA},
            "vault_id": {"S": "vault-owner"},
            "user_id": {"S": user_id},
            "s3_key": {"S": f"vaults/vault-owner/files/{ITEM_ID}/blob"},
            "encrypted_metadata": {"B": b"opaque"},
            "upload_status": {"S": "COMPLETE"},
            "upload_id": {"S": "u1"},
            "created_at": {"N": "1234567890"},
            "updated_at": {"N": "1234567890"},
            "version": {"N": "1"},
        }
    }


# Every user-facing ItemService operation that takes (user_id, item_id), invoked
# AS THE ATTACKER. The ownership check in each must fire before any side effect.
OPERATIONS = [
    ("get_item", lambda s: s.get_item(ATTACKER, ITEM_ID)),
    ("get_download_url", lambda s: s.get_download_url(ATTACKER, ITEM_ID)),
    ("delete_item", lambda s: s.delete_item(ATTACKER, ITEM_ID)),
    (
        "complete_upload",
        lambda s: s.complete_upload(
            ATTACKER,
            ITEM_ID,
            CompleteItemUploadRequestContent(
                upload_id="u1", parts=[UploadPart(part_number=1, e_tag='"e1"')]
            ),
        ),
    ),
    (
        "create_upload_part_urls",
        lambda s: s.create_upload_part_urls(
            ATTACKER, ITEM_ID, CreateUploadPartUrlsRequestContent(upload_id="u1", part_numbers=[1])
        ),
    ),
    (
        "abort_upload",
        lambda s: s.abort_upload(ATTACKER, ITEM_ID, AbortItemUploadRequestContent(upload_id="u1")),
    ),
]


class TestVaultDataIsolation:
    """Property 4: a user cannot touch another user's item via any operation."""

    @pytest.mark.parametrize("label, operation", OPERATIONS, ids=[o[0] for o in OPERATIONS])
    def test_cross_user_access_is_denied_with_no_side_effects(
        self, item_service, dynamodb_stubber, label, operation
    ):
        # Only get_item is queued; the item belongs to OWNER. If the operation
        # reaches S3 or a mutating DynamoDB call as the attacker, that unstubbed
        # request fails the test — so passing proves zero side effects.
        dynamodb_stubber.add_response(
            "get_item", _owner_item(OWNER), {"TableName": TABLE, "Key": ANY}
        )

        with pytest.raises(NotFoundError, match="Item not found"):
            operation(item_service)

        dynamodb_stubber.assert_no_pending_responses()

    def test_nonexistent_item_is_denied_identically(self, item_service, dynamodb_stubber):
        # A probe for an id that doesn't exist returns the same NotFoundError as a
        # foreign-owned one, so the API doesn't leak which item ids exist.
        dynamodb_stubber.add_response("get_item", {}, {"TableName": TABLE, "Key": ANY})
        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.delete_item(ATTACKER, ITEM_ID)

    def test_positive_control_owner_is_not_blocked(self, item_service, dynamodb_stubber):
        # Non-vacuity: the SAME item is returned for its owner, proving the denials
        # above are the ownership check and not some unrelated failure.
        dynamodb_stubber.add_response(
            "get_item", _owner_item(OWNER), {"TableName": TABLE, "Key": ANY}
        )
        item = item_service.get_item(OWNER, ITEM_ID)
        assert item is not None
        assert item["item_id"] == ITEM_ID
        assert item["user_id"] == OWNER
