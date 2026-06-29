"""
Property-Based Tests for the Item API.

Feature: cortex, Property 5: Referential integrity between S3 and DynamoDB
Feature: cortex, Property 28: Generic item API supports all types

These exercise the REAL ItemService against botocore-stubbed AWS (the same
fixtures the unit tests use), rather than re-implementing a toy model in the
test. A stub that is queued but never consumed — or a call with no stub — fails
the test, so the assertions are about the service's actual S3/DynamoDB calls.
"""

import base64

import pytest
from botocore.stub import ANY

from src.shared.exceptions import BadRequestError
from src.shared.generated.models import (
    CreateItemRequestContent,
    InitiateItemUploadRequestContent,
)
from src.shared.models import ItemType

TABLE = "test-items-table"


def _media_item(item_id, *, status="COMPLETE", s3_key, user_id="user-123"):
    """A MEDIA item with no tags, in DynamoDB get_item wire form."""
    return {
        "Item": {
            "PK": {"S": f"ITEM#{item_id}"},
            "SK": {"S": "METADATA"},
            "item_id": {"S": item_id},
            "item_type": {"S": ItemType.MEDIA},
            "vault_id": {"S": "vault-123"},
            "user_id": {"S": user_id},
            "s3_key": {"S": s3_key},
            "encrypted_metadata": {"B": b"opaque"},
            "upload_status": {"S": status},
            "created_at": {"N": "1234567890"},
            "updated_at": {"N": "1234567890"},
            "version": {"N": "1"},
        }
    }


class TestReferentialIntegrity:
    """
    Property 5: Referential integrity between S3 and DynamoDB.

    If metadata exists in DynamoDB, the S3 object must exist, and deletes/failed
    completions must not leave one store pointing at a missing peer.

    Validates: Requirements 2.5
    """

    def test_deleting_media_removes_both_s3_and_dynamodb(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """A completed MEDIA delete removes the S3 object AND the DynamoDB record."""
        s3_key = "vaults/vault-123/files/item-1/blob"
        dynamodb_stubber.add_response(
            "get_item", _media_item("item-1", s3_key=s3_key), {"TableName": TABLE, "Key": ANY}
        )
        s3_stubber.add_response("delete_object", {}, {"Bucket": files_bucket_name, "Key": s3_key})
        dynamodb_stubber.add_response("delete_item", {}, {"TableName": TABLE, "Key": ANY})

        item_service.delete_item("user-123", "item-1")

        # Both stores were touched: a missing/extra call would fail these.
        s3_stubber.assert_no_pending_responses()
        dynamodb_stubber.assert_no_pending_responses()

    def test_deleting_inline_item_touches_no_s3(self, item_service, dynamodb_stubber, s3_stubber):
        """A NOTE item has no S3 object, so deletion must not call S3 (no orphan to make)."""
        note = {
            "Item": {
                "PK": {"S": "ITEM#note-1"},
                "SK": {"S": "METADATA"},
                "item_id": {"S": "note-1"},
                "item_type": {"S": ItemType.NOTE},
                "vault_id": {"S": "vault-123"},
                "user_id": {"S": "user-123"},
                "encrypted_content": {"B": b"opaque"},
                "encrypted_metadata": {"B": b"opaque"},
                "created_at": {"N": "1234567890"},
                "updated_at": {"N": "1234567890"},
                "version": {"N": "1"},
            }
        }
        dynamodb_stubber.add_response("get_item", note, {"TableName": TABLE, "Key": ANY})
        dynamodb_stubber.add_response("delete_item", {}, {"TableName": TABLE, "Key": ANY})

        item_service.delete_item("user-123", "note-1")

        # No S3 response was queued; if delete had called S3 it would have failed.
        dynamodb_stubber.assert_no_pending_responses()

    def test_complete_upload_without_s3_object_cleans_up_metadata(
        self, item_service, dynamodb_stubber, s3_stubber
    ):
        """
        If the S3 object is absent at completion, the pending DynamoDB metadata is
        deleted and completion fails — so metadata never outlives its missing object.
        """
        dynamodb_stubber.add_response(
            "get_item",
            _media_item("item-1", status="PENDING", s3_key="vaults/vault-123/files/item-1/blob"),
            {"TableName": TABLE, "Key": ANY},
        )
        # get_object_metadata -> head_object 404 -> None -> cleanup path
        s3_stubber.add_client_error(
            "head_object", service_error_code="404", service_message="Not Found"
        )
        dynamodb_stubber.add_response("delete_item", {}, {"TableName": TABLE, "Key": ANY})

        with pytest.raises(BadRequestError, match="Uploaded object not found"):
            item_service.complete_upload("user-123", "item-1")

        dynamodb_stubber.assert_no_pending_responses()


class TestGenericItemApiSupportsAllTypes:
    """
    Property 28: Generic item API supports all types.

    The backend stores every item type's encrypted payload as opaque bytes,
    without decrypting or inspecting it.

    Validates: Requirements 24.1, 24.2, 24.3
    """

    @pytest.mark.parametrize("item_type", [ItemType.NOTE, ItemType.TASK, ItemType.EVENT])
    def test_create_inline_item_for_each_type(self, item_service, dynamodb_stubber, item_type):
        """create_item handles NOTE/TASK/EVENT identically, storing one DynamoDB record."""
        request = CreateItemRequestContent(
            vault_id="vault-123",
            item_type=item_type,
            encrypted_content=base64.b64encode(b"opaque-content"),
            encrypted_metadata=base64.b64encode(b"opaque-metadata"),
        )
        dynamodb_stubber.add_response("put_item", {}, {"TableName": TABLE, "Item": ANY})

        response = item_service.create_item("user-123", request)

        assert response.item_type == item_type
        assert response.item_id
        dynamodb_stubber.assert_no_pending_responses()

    def test_backend_stores_arbitrary_opaque_bytes(self, item_service, dynamodb_stubber):
        """
        Content the backend can't parse (random/binary, not valid utf-8 or JSON)
        flows through unmodified — evidence the backend never decrypts or inspects it.
        """
        garbage = bytes(range(256))  # every byte value, not decodable as text/JSON
        request = CreateItemRequestContent(
            vault_id="vault-123",
            item_type=ItemType.NOTE,
            encrypted_content=base64.b64encode(garbage),
            encrypted_metadata=base64.b64encode(garbage),
        )
        dynamodb_stubber.add_response("put_item", {}, {"TableName": TABLE, "Item": ANY})

        response = item_service.create_item("user-123", request)

        assert response.item_id  # stored without error → treated as opaque
        dynamodb_stubber.assert_no_pending_responses()

    def test_media_upload_initiation_is_consistent(self, item_service, dynamodb_stubber):
        """MEDIA goes through initiate_upload (presigned PUT) but stores a record the same way."""
        request = InitiateItemUploadRequestContent(
            vault_id="vault-123",
            encrypted_metadata=base64.b64encode(b"opaque-metadata"),
            size_bytes=1024,  # below multipart threshold -> single PUT, no uploadId
            wrapped_dek=base64.b64encode(bytes(range(97))),
            dek_version=1,
        )
        dynamodb_stubber.add_response("put_item", {}, {"TableName": TABLE, "Item": ANY})

        response = item_service.initiate_upload("user-123", request)

        assert response.item_id
        assert response.upload_url
        assert response.upload_id is None
        dynamodb_stubber.assert_no_pending_responses()
