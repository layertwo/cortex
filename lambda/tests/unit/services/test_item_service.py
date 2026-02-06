"""
Unit tests for ItemService.

Tests the item service layer for creating items, initiating uploads,
and completing uploads for all item types.

Schema: PK: ITEM#{itemId}, SK: METADATA (constant)
GSI1: VAULT#{vaultId}#TYPE#{itemType} for type-filtered queries
GSI2: VAULT#{vaultId} for listing all items in vault
"""

import uuid
from datetime import datetime, timezone

import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)
from botocore.stub import ANY

from src.shared.models import (
    CompleteUploadRequest,
    CreateItemRequest,
    InitiateUploadRequest,
    ItemType,
)


class TestCreateItem:
    """Tests for create_item method (NOTE, TASK, EVENT items)."""

    def test_create_note_item(self, item_service, dynamodb_stubber):
        """Test creating a NOTE item with inline content and tags uses transact_write_items."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.NOTE,
            encrypted_content=b"encrypted-note-content",
            encrypted_metadata=b"encrypted-metadata",
            encrypted_tags=[b"tag1", b"tag2"],
        )

        dynamodb_stubber.add_response(
            "transact_write_items", {}, {"TransactItems": ANY}
        )

        response = item_service.create_item("user-123", request)

        assert response.item_id is not None
        assert response.item_type == ItemType.NOTE
        assert isinstance(response.created_at, datetime)

    def test_create_task_item_with_date_bucket(self, item_service, dynamodb_stubber):
        """Test creating a TASK item with date bucket."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.TASK,
            encrypted_content=b"encrypted-task-content",
            encrypted_metadata=b"encrypted-metadata",
            encrypted_date_bucket=b"encrypted-bucket",
            time_bucket="2026-01-24T14:00",
        )

        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-items-table", "Item": ANY}
        )

        response = item_service.create_item("user-123", request)

        assert response.item_id is not None
        assert response.item_type == ItemType.TASK
        assert isinstance(response.created_at, datetime)

    def test_create_event_item(self, item_service, dynamodb_stubber):
        """Test creating an EVENT item."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.EVENT,
            encrypted_content=b"encrypted-event-content",
            encrypted_metadata=b"encrypted-metadata",
        )

        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-items-table", "Item": ANY}
        )

        response = item_service.create_item("user-123", request)

        assert response.item_id is not None
        assert response.item_type == ItemType.EVENT

    def test_create_item_without_tags_uses_put_item(self, item_service, dynamodb_stubber):
        """Test that creating item without tags uses simple put_item."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.NOTE,
            encrypted_content=b"content",
            encrypted_metadata=b"metadata",
        )

        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-items-table", "Item": ANY}
        )

        response = item_service.create_item("user-123", request)

        assert response.item_id is not None


class TestInitiateUpload:
    """Tests for initiate_upload method (MEDIA items)."""

    def test_initiate_small_file_upload(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test initiating upload for small file (<100MB)."""
        request = InitiateUploadRequest(
            vault_id="vault-123",
            encrypted_metadata=b"encrypted-metadata",
            size_bytes=50 * 1024 * 1024,  # 50MB
            content_type="image/jpeg",
            encrypted_tags=[b"tag1"],
        )

        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-items-table", "Item": ANY}
        )

        response = item_service.initiate_upload("user-123", request)

        assert response.item_id is not None
        assert response.upload_url is not None
        assert response.s3_key is not None
        assert response.upload_id is None  # No multipart for small files
        assert isinstance(response.expires_at, datetime)

    def test_initiate_large_file_upload(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test initiating multipart upload for large file (>100MB)."""
        request = InitiateUploadRequest(
            vault_id="vault-123",
            encrypted_metadata=b"encrypted-metadata",
            size_bytes=150 * 1024 * 1024,  # 150MB
            content_type="video/mp4",
        )

        s3_stubber.add_response(
            "create_multipart_upload",
            {
                "UploadId": "test-upload-id",
                "Bucket": files_bucket_name,
                "Key": "vaults/vault-123/files/test-item/test",
            },
            {
                "Bucket": files_bucket_name,
                "Key": ANY,
                "ContentType": "video/mp4",
                "ServerSideEncryption": "AES256",
            },
        )

        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-items-table", "Item": ANY}
        )

        response = item_service.initiate_upload("user-123", request)

        assert response.item_id is not None
        assert response.upload_url is not None
        assert response.s3_key is not None
        assert response.upload_id == "test-upload-id"


class TestCompleteUpload:
    """Tests for method."""

    def test_complete_upload_success(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test successfully completing an upload."""
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(item_id=item_id, vault_id="vault-123")

        # get_item with new schema: PK=ITEM#{itemId}
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                    "upload_status": {"S": "PENDING"},
                }
            },
            {"TableName": "test-items-table", "Key": {"PK": f"ITEM#{item_id}"}},
        )

        s3_stubber.add_response(
            "head_object",
            {"ContentLength": 1000, "ContentType": "image/jpeg"},
            {"Bucket": files_bucket_name, "Key": f"vaults/vault-123/files/{item_id}/test"},
        )

        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "upload_status": {"S": "COMPLETE"},
                    "updated_at": {"N": str(int(datetime.now(tz=timezone.utc).timestamp()))},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {"PK": f"ITEM#{item_id}"},
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = item_service.complete_upload("user-123", request)

        assert response.item_id == item_id

    def test_complete_upload_item_not_found(self, item_service, dynamodb_stubber):
        """Test completing upload when item doesn't exist."""
        request = CompleteUploadRequest(item_id="nonexistent-item", vault_id="vault-123")

        dynamodb_stubber.add_response("get_item", {}, {"TableName": "test-items-table", "Key": ANY})

        with pytest.raises(NotFoundError):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_unauthorized(self, item_service, dynamodb_stubber):
        """Test completing upload when user doesn't own the item."""
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(item_id=item_id, vault_id="vault-123")

        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "different-user"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        with pytest.raises(NotFoundError):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_s3_object_missing(self, item_service, dynamodb_stubber, s3_stubber):
        """Test completing upload when S3 object doesn't exist."""
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(item_id=item_id, vault_id="vault-123")

        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        s3_stubber.add_client_error(
            "head_object", service_error_code="404", service_message="Not Found"
        )

        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        with pytest.raises(Exception):
            item_service.complete_upload("user-123", request)


class TestCleanupFailedUpload:
    """Tests for cleanup_failed_upload method."""

    def test_cleanup_with_s3_object(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test cleanup when S3 object exists."""
        item_id = str(uuid.uuid4())
        s3_key = f"vaults/vault-123/files/{item_id}/test"

        s3_stubber.add_response("delete_object", {}, {"Bucket": files_bucket_name, "Key": s3_key})
        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        item_service.cleanup_failed_upload(item_id, s3_key)

    def test_cleanup_without_s3_object(self, item_service, dynamodb_stubber):
        """Test cleanup when S3 object doesn't exist."""
        item_id = str(uuid.uuid4())

        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        item_service.cleanup_failed_upload(item_id, None)

    def test_cleanup_with_multipart_upload(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test cleanup when multipart upload needs to be aborted."""
        item_id = str(uuid.uuid4())
        s3_key = f"vaults/vault-123/files/{item_id}/test"
        upload_id = "test-upload-id-123"

        s3_stubber.add_response(
            "abort_multipart_upload",
            {},
            {"Bucket": files_bucket_name, "Key": s3_key, "UploadId": upload_id},
        )
        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        item_service.cleanup_failed_upload(item_id, s3_key, upload_id)


class TestListItems:
    """Tests for list_items method."""

    def test_list_items_all_types(self, item_service, dynamodb_stubber):
        """Test listing all items without type filter using GSI2."""
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "ITEM#item-1"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "NOTE"},
                        "vault_id": {"S": "vault-123"},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-1"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    },
                    {
                        "PK": {"S": "ITEM#item-2"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-2"},
                        "item_type": {"S": "MEDIA"},
                        "vault_id": {"S": "vault-123"},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-2"},
                        "s3_key": {"S": "vaults/vault-123/files/item-2/file.jpg"},
                        "size_bytes": {"N": "1024"},
                        "upload_status": {"S": "COMPLETE"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    },
                ],
                "Count": 2,
            },
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": ANY,
                "ScanIndexForward": False,
                "Limit": 50,
            },
        )

        items, next_token = item_service.list_items(
            user_id="user-123",
            vault_id="vault-123",
            item_type=None,
            page_size=50,
            next_token=None,
            sort_order="desc",
        )

        assert len(items) == 2
        assert items[0]["item_id"] == "item-1"
        assert items[1]["item_id"] == "item-2"
        assert next_token is None

    def test_list_items_with_type_filter(self, item_service, dynamodb_stubber):
        """Test listing items filtered by type using GSI1."""
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "ITEM#item-1"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "MEDIA"},
                        "vault_id": {"S": "vault-123"},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata"},
                        "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                        "size_bytes": {"N": "2048"},
                        "upload_status": {"S": "COMPLETE"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    }
                ],
                "Count": 1,
            },
            {
                "TableName": "test-items-table",
                "IndexName": "GSI1",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": ANY,
                "ScanIndexForward": False,
                "Limit": 50,
            },
        )

        items, next_token = item_service.list_items(
            user_id="user-123",
            vault_id="vault-123",
            item_type=ItemType.MEDIA,
            page_size=50,
            next_token=None,
            sort_order="desc",
        )

        assert len(items) == 1
        assert items[0]["item_type"] == "MEDIA"
        assert next_token is None


class TestGetItem:
    """Tests for get_item method."""

    def test_get_item_success(self, item_service, dynamodb_stubber):
        """Test successfully retrieving an item."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "NOTE"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_content": {"B": b"encrypted-content"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": {"PK": "ITEM#item-1"}},
        )

        item = item_service.get_item("user-123", "item-1")

        assert item is not None
        assert item["item_id"] == "item-1"
        assert item["item_type"] == "NOTE"
        assert item["user_id"] == "user-123"

    def test_get_item_not_found(self, item_service, dynamodb_stubber):
        """Test retrieving non-existent item."""
        dynamodb_stubber.add_response(
            "get_item", {}, {"TableName": "test-items-table", "Key": {"PK": "ITEM#nonexistent"}}
        )

        with pytest.raises(NotFoundError):
            item_service.get_item("user-123", "nonexistent")

    def test_get_item_unauthorized(self, item_service, dynamodb_stubber):
        """Test retrieving item owned by different user."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "NOTE"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "other-user"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.get_item("user-123", "item-1")

    def test_get_item_filters_pending(self, item_service, dynamodb_stubber):
        """Test that PENDING items are filtered out."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "upload_status": {"S": "PENDING"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        item = item_service.get_item("user-123", "item-1")

        assert item is None


class TestGetDownloadUrl:
    """Tests for get_download_url method."""

    def test_get_download_url_success(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test successfully generating download URL for MEDIA item."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "upload_status": {"S": "COMPLETE"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1024,
                "ETag": '"abc123"',
                "LastModified": datetime(2026, 1, 24, 12, 0, 0),
            },
            {"Bucket": files_bucket_name, "Key": "vaults/vault-123/files/item-1/file.jpg"},
        )

        download_url, expires_at, encrypted_metadata, s3_key = item_service.get_download_url(
            "user-123", "item-1"
        )

        assert s3_key == "vaults/vault-123/files/item-1/file.jpg"
        assert encrypted_metadata == b"encrypted-metadata"
        assert expires_at is not None

    def test_get_download_url_item_not_found(self, item_service, dynamodb_stubber):
        """Test download URL when item doesn't exist."""
        dynamodb_stubber.add_response("get_item", {}, {"TableName": "test-items-table", "Key": ANY})

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.get_download_url("user-123", "nonexistent")

    def test_get_download_url_unauthorized(self, item_service, dynamodb_stubber):
        """Test download URL when user doesn't own item."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "other-user"},
                    "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.get_download_url("user-123", "item-1")

    def test_get_download_url_not_media_type(self, item_service, dynamodb_stubber):
        """Test download URL for non-MEDIA item type."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "NOTE"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        with pytest.raises(BadRequestError, match="Download URL only available for MEDIA items"):
            item_service.get_download_url("user-123", "item-1")

    def test_get_download_url_pending_upload(self, item_service, dynamodb_stubber):
        """Test download URL when upload is still pending."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "upload_status": {"S": "PENDING"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        with pytest.raises(BadRequestError, match="Item upload not yet complete"):
            item_service.get_download_url("user-123", "item-1")


class TestDeleteItem:
    """Test suite for delete_item method."""

    def test_delete_media_item_success(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test successful deletion of MEDIA item with S3 object."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "upload_status": {"S": "COMPLETE"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        s3_stubber.add_response(
            "delete_object",
            {},
            {"Bucket": files_bucket_name, "Key": "vaults/vault-123/files/item-1/file.jpg"},
        )
        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        item_service.delete_item("user-123", "item-1")

    def test_delete_note_item_success(self, item_service, dynamodb_stubber):
        """Test successful deletion of NOTE item (no S3 object)."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "NOTE"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_content": {"B": b"encrypted-content"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        item_service.delete_item("user-123", "item-1")

    def test_delete_item_not_found(self, item_service, dynamodb_stubber):
        """Test deletion when item doesn't exist."""
        dynamodb_stubber.add_response("get_item", {}, {"TableName": "test-items-table", "Key": ANY})

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.delete_item("user-123", "item-1")

    def test_delete_item_unauthorized(self, item_service, dynamodb_stubber):
        """Test deletion when user doesn't own the item."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "other-user"},
                    "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.delete_item("user-123", "item-1")

    def test_delete_media_item_pending_upload(
        self, item_service, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test deletion of MEDIA item with pending multipart upload."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": "vaults/vault-123/files/item-1/file.jpg"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "upload_status": {"S": "PENDING"},
                    "upload_id": {"S": "test-upload-id"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        s3_stubber.add_response(
            "abort_multipart_upload",
            {},
            {
                "Bucket": files_bucket_name,
                "Key": "vaults/vault-123/files/item-1/file.jpg",
                "UploadId": "test-upload-id",
            },
        )
        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        item_service.delete_item("user-123", "item-1")

    def test_delete_note_item_with_tags_cleans_up_tag_rows(self, item_service, dynamodb_stubber):
        """Test that deleting item with tags also deletes tag index rows."""

        tag1 = b"encrypted-tag-1"
        tag2 = b"encrypted-tag-2"

        # Stub get_item to return item with tags
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "NOTE"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_content": {"B": b"encrypted-content"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "encrypted_tags": {"L": [{"B": tag1}, {"B": tag2}]},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )

        # Stub delete of item row
        dynamodb_stubber.add_response(
            "delete_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        # Stub batch_write_item for tag row cleanup
        dynamodb_stubber.add_response(
            "batch_write_item",
            {"UnprocessedItems": {}},
            {"RequestItems": ANY},
        )

        item_service.delete_item("user-123", "item-1")
