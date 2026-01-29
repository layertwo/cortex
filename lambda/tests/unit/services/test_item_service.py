"""
Unit tests for ItemService.

Tests the item service layer for creating items, initiating uploads,
and completing uploads for all item types.
"""

import uuid
from datetime import datetime, timezone

import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
)
from botocore.stub import ANY

from src.api.services.item_service import ItemService
from src.shared.models import (
    CompleteUploadRequest,
    CreateItemRequest,
    InitiateUploadRequest,
    ItemType,
)


@pytest.fixture
def items_table_name():
    """DynamoDB items table name."""
    return "test-items-table"


@pytest.fixture
def s3_bucket_name():
    """S3 bucket name."""
    return "test-bucket"


@pytest.fixture
def item_service(boto_session, items_table_name, s3_bucket_name):
    """Create an ItemService instance for testing."""
    return ItemService(
        session=boto_session,
        items_table_name=items_table_name,
        s3_bucket_name=s3_bucket_name,
    )


class TestCreateItem:
    """Tests for create_item method (NOTE, TASK, EVENT items)."""

    def test_create_note_item(self, item_service, dynamodb_stubber):
        """Test creating a NOTE item with inline content."""
        # Prepare request
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.NOTE,
            encrypted_content=b"encrypted-note-content",
            encrypted_metadata=b"encrypted-metadata",
            encrypted_tags=[b"tag1", b"tag2"],
        )

        # Configure stubber
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = item_service.create_item("user-123", request)

        # Verify response
        assert response.item_id is not None
        assert response.item_type == ItemType.NOTE
        assert isinstance(response.created_at, datetime)

    def test_create_task_item_with_date_bucket(self, item_service, dynamodb_stubber):
        """Test creating a TASK item with date bucket."""
        # Prepare request
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.TASK,
            encrypted_content=b"encrypted-task-content",
            encrypted_metadata=b"encrypted-metadata",
            encrypted_date_bucket=b"encrypted-bucket",
            time_bucket="2026-01-24T14:00",
        )

        # Configure stubber
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = item_service.create_item("user-123", request)

        # Verify response
        assert response.item_id is not None
        assert response.item_type == ItemType.TASK
        assert isinstance(response.created_at, datetime)

    def test_create_event_item(self, item_service, dynamodb_stubber):
        """Test creating an EVENT item."""
        # Prepare request
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type=ItemType.EVENT,
            encrypted_content=b"encrypted-event-content",
            encrypted_metadata=b"encrypted-metadata",
        )

        # Configure stubber
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = item_service.create_item("user-123", request)

        # Verify response
        assert response.item_id is not None
        assert response.item_type == ItemType.EVENT


class TestInitiateUpload:
    """Tests for initiate_upload method (MEDIA items)."""

    def test_initiate_small_file_upload(self, item_service, dynamodb_stubber, s3_stubber):
        """Test initiating upload for small file (<100MB)."""
        # Prepare request
        request = InitiateUploadRequest(
            vault_id="vault-123",
            encrypted_metadata=b"encrypted-metadata",
            size_bytes=50 * 1024 * 1024,  # 50MB
            content_type="image/jpeg",
            encrypted_tags=[b"tag1"],
        )

        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = item_service.initiate_upload("user-123", request)

        # Verify response
        assert response.item_id is not None
        assert response.upload_url is not None
        assert response.s3_key is not None
        assert response.upload_id is None  # No multipart for small files
        assert isinstance(response.expires_at, datetime)

    def test_initiate_large_file_upload(self, item_service, dynamodb_stubber, s3_stubber):
        """Test initiating multipart upload for large file (>100MB)."""
        # Prepare request
        request = InitiateUploadRequest(
            vault_id="vault-123",
            encrypted_metadata=b"encrypted-metadata",
            size_bytes=150 * 1024 * 1024,  # 150MB
            content_type="video/mp4",
        )

        # Configure S3 stubber for multipart upload
        # Note: Response must have actual string values, not ANY
        s3_stubber.add_response(
            "create_multipart_upload",
            {
                "UploadId": "test-upload-id",
                "Bucket": "test-bucket",
                "Key": "vaults/vault-123/files/test-item/test",  # Actual key value
            },
            {
                "Bucket": "test-bucket",
                "Key": ANY,  # Expected params can use ANY
                "ContentType": "video/mp4",
                "ServerSideEncryption": "AES256",
            },
        )

        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = item_service.initiate_upload("user-123", request)

        # Verify response
        assert response.item_id is not None
        assert response.upload_url is not None
        assert response.s3_key is not None
        assert response.upload_id == "test-upload-id"  # Multipart upload ID present


class TestCompleteUpload:
    """Tests for complete_upload method."""

    def test_complete_upload_success(self, item_service, dynamodb_stubber, s3_stubber):
        """Test successfully completing an upload."""
        # Prepare request
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(
            item_id=item_id,
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber for get_item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                    "upload_status": {"S": "PENDING"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": "VAULT#vault-123",
                    "SK": f"ITEM#MEDIA#{item_id}",
                },
            },
        )

        # Configure S3 stubber for head_object
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1000,
                "ContentType": "image/jpeg",
            },
            {
                "Bucket": "test-bucket",
                "Key": f"vaults/vault-123/files/{item_id}/test",
            },
        )

        # Configure DynamoDB stubber for conditional update_item
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
                "Key": {
                    "PK": "VAULT#vault-123",
                    "SK": f"ITEM#MEDIA#{item_id}",
                },
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,  # Conditional update for TOCTOU protection
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = item_service.complete_upload("user-123", request)

        # Verify response
        assert response.item_id == item_id
        assert isinstance(response.uploaded_at, datetime)

    def test_complete_upload_item_not_found(self, item_service, dynamodb_stubber):
        """Test completing upload when item doesn't exist."""
        # Prepare request
        request = CompleteUploadRequest(
            item_id="nonexistent-item",
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber to return no item
        dynamodb_stubber.add_response(
            "get_item",
            {},  # Empty response
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(NotFoundError):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_unauthorized(self, item_service, dynamodb_stubber):
        """Test completing upload when user doesn't own the item."""
        # Prepare request
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(
            item_id=item_id,
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber with different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "different-user"},  # Different user
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(ForbiddenError):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_s3_object_missing(self, item_service, dynamodb_stubber, s3_stubber):
        """Test completing upload when S3 object doesn't exist."""
        # Prepare request
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(
            item_id=item_id,
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        s3_stubber.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
        )

        # Configure DynamoDB stubber for cleanup (delete_item)
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(InternalServerError, match="Upload verification failed"):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_s3_object_missing_with_multipart(
        self, item_service, dynamodb_stubber, s3_stubber
    ):
        """Test completing upload when S3 object doesn't exist and multipart upload needs abort."""
        # Prepare request
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(
            item_id=item_id,
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber - item has upload_id
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                    "upload_id": {"S": "test-upload-id-123"},  # Multipart upload
                }
            },
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # S3 object doesn't exist
        s3_stubber.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
        )

        # Configure S3 stubber for abort_multipart_upload
        s3_stubber.add_response(
            "abort_multipart_upload",
            {},
            {
                "Bucket": "test-bucket",
                "Key": f"vaults/vault-123/files/{item_id}/test",
                "UploadId": "test-upload-id-123",
            },
        )

        # Configure DynamoDB stubber for cleanup (delete_item)
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(InternalServerError, match="Upload verification failed"):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_toctou_race_condition(
        self, item_service, dynamodb_stubber, s3_stubber
    ):
        """
        Test TOCTOU race condition protection during upload completion.

        This test simulates a scenario where:
        1. S3 object exists during initial verification (head_object succeeds)
        2. Conditional DynamoDB update fails (simulating concurrent modification)
        3. S3 object is deleted between verification and update (head_object fails)
        4. System detects race condition and cleans up orphaned metadata

        Security: Prevents referential integrity violation (A04:2021 - Insecure Design)
        """
        # Prepare request
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(
            item_id=item_id,
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber for get_item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                    "upload_status": {"S": "PENDING"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": "VAULT#vault-123",
                    "SK": f"ITEM#MEDIA#{item_id}",
                },
            },
        )

        # First head_object succeeds (object exists during verification)
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1000,
                "ContentType": "image/jpeg",
                "ETag": '"abc123"',
            },
            {
                "Bucket": "test-bucket",
                "Key": f"vaults/vault-123/files/{item_id}/test",
            },
        )

        # Conditional update fails (simulating race condition or concurrent modification)
        dynamodb_stubber.add_client_error(
            "update_item",
            service_error_code="ConditionalCheckFailedException",
            service_message="The conditional request failed",
        )

        # Second head_object fails (object was deleted during race window)
        s3_stubber.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
        )

        # Configure DynamoDB stubber for cleanup (delete_item)
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(InternalServerError, match="object was deleted during completion"):
            item_service.complete_upload("user-123", request)

    def test_complete_upload_with_version_id(self, item_service, dynamodb_stubber, s3_stubber):
        """Test completing upload with S3 versioning enabled (stores version ID)."""
        # Prepare request
        item_id = str(uuid.uuid4())
        request = CompleteUploadRequest(
            item_id=item_id,
            vault_id="vault-123",
        )

        # Configure DynamoDB stubber for get_item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                    "upload_status": {"S": "PENDING"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": "VAULT#vault-123",
                    "SK": f"ITEM#MEDIA#{item_id}",
                },
            },
        )

        # Configure S3 stubber for head_object with version ID
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1000,
                "ContentType": "image/jpeg",
                "VersionId": "version-abc123",  # Versioned bucket
            },
            {
                "Bucket": "test-bucket",
                "Key": f"vaults/vault-123/files/{item_id}/test",
            },
        )

        # Configure DynamoDB stubber for update_item (should include version_id)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "upload_status": {"S": "COMPLETE"},
                    "updated_at": {"N": str(int(datetime.now(tz=timezone.utc).timestamp()))},
                    "s3_version_id": {"S": "version-abc123"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": "VAULT#vault-123",
                    "SK": f"ITEM#MEDIA#{item_id}",
                },
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,  # Conditional update
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = item_service.complete_upload("user-123", request)

        # Verify response
        assert response.item_id == item_id
        assert isinstance(response.uploaded_at, datetime)


class TestCleanupFailedUpload:
    """Tests for cleanup_failed_upload method."""

    def test_cleanup_with_s3_object(self, item_service, dynamodb_stubber, s3_stubber):
        """Test cleanup when S3 object exists."""
        item_id = str(uuid.uuid4())
        s3_key = f"vaults/vault-123/files/{item_id}/test"

        # Configure S3 stubber
        s3_stubber.add_response(
            "delete_object",
            {},
            {
                "Bucket": "test-bucket",
                "Key": s3_key,
            },
        )

        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        item_service.cleanup_failed_upload("vault-123", item_id, s3_key)

    def test_cleanup_without_s3_object(self, item_service, dynamodb_stubber):
        """Test cleanup when S3 object doesn't exist."""
        item_id = str(uuid.uuid4())

        # Configure DynamoDB stubber only
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        item_service.cleanup_failed_upload("vault-123", item_id, None)

    def test_cleanup_with_multipart_upload(self, item_service, dynamodb_stubber, s3_stubber):
        """Test cleanup when multipart upload needs to be aborted."""
        item_id = str(uuid.uuid4())
        s3_key = f"vaults/vault-123/files/{item_id}/test"
        upload_id = "test-upload-id-123"

        # Configure S3 stubber for abort_multipart_upload
        s3_stubber.add_response(
            "abort_multipart_upload",
            {},
            {
                "Bucket": "test-bucket",
                "Key": s3_key,
                "UploadId": upload_id,
            },
        )

        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        item_service.cleanup_failed_upload("vault-123", item_id, s3_key, upload_id)


class TestListItems:
    """Tests for list_items method."""

    def test_list_items_all_types(self, item_service, dynamodb_stubber):
        """Test listing all items without type filter."""
        # Configure stubber for query
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "VAULT#vault-123"},
                        "SK": {"S": "ITEM#NOTE#item-1"},
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
                        "PK": {"S": "VAULT#vault-123"},
                        "SK": {"S": "ITEM#MEDIA#item-2"},
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
        """Test listing items filtered by type using GSI."""
        # Configure stubber for GSI query
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "VAULT#vault-123"},
                        "SK": {"S": "ITEM#MEDIA#item-1"},
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

    def test_list_items_filters_pending_uploads(self, item_service, dynamodb_stubber):
        """Test that PENDING uploads are filtered out from results using FilterExpression."""
        # Configure stubber - DynamoDB filters at query level, so only COMPLETE item returned
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "VAULT#vault-123"},
                        "SK": {"S": "ITEM#MEDIA#item-1"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "MEDIA"},
                        "vault_id": {"S": "vault-123"},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata"},
                        "upload_status": {"S": "COMPLETE"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    },
                ],
                "Count": 1,
            },
            {
                "TableName": "test-items-table",
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

        # Should only return COMPLETE item
        assert len(items) == 1
        assert items[0]["item_id"] == "item-1"
        assert items[0]["upload_status"] == "COMPLETE"

    def test_list_items_with_pagination(self, item_service, dynamodb_stubber):
        """Test listing items with pagination token."""
        # Configure stubber with LastEvaluatedKey
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "VAULT#vault-123"},
                        "SK": {"S": "ITEM#NOTE#item-1"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "NOTE"},
                        "vault_id": {"S": "vault-123"},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    }
                ],
                "Count": 1,
                "LastEvaluatedKey": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#NOTE#item-1"},
                },
            },
            {
                "TableName": "test-items-table",
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

        assert len(items) == 1
        assert next_token is not None  # Should have pagination token


class TestGetItem:
    """Tests for get_item method."""

    def test_get_item_success(self, item_service, dynamodb_stubber):
        """Test successfully retrieving an item."""
        # Configure stubber - will try each type until found
        # First try MEDIA (not found)
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Second try NOTE (found)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#NOTE#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        item = item_service.get_item("user-123", "vault-123", "item-1")

        assert item is not None
        assert item["item_id"] == "item-1"
        assert item["item_type"] == "NOTE"
        assert item["user_id"] == "user-123"

    def test_get_item_not_found(self, item_service, dynamodb_stubber):
        """Test retrieving non-existent item."""
        # Configure stubber - all types return empty
        for _ in range(4):  # MEDIA, NOTE, TASK, EVENT
            dynamodb_stubber.add_response(
                "get_item",
                {},
                {
                    "TableName": "test-items-table",
                    "Key": ANY,
                },
            )

        item = item_service.get_item("user-123", "vault-123", "nonexistent")

        assert item is None

    def test_get_item_unauthorized(self, item_service, dynamodb_stubber):
        """Test retrieving item owned by different user."""
        # Configure stubber - item found but owned by different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#NOTE#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(ForbiddenError, match="Access denied to item"):
            item_service.get_item("user-123", "vault-123", "item-1")

    def test_get_item_filters_pending(self, item_service, dynamodb_stubber):
        """Test that PENDING items are filtered out."""
        # Configure stubber - item found but status is PENDING
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        item = item_service.get_item("user-123", "vault-123", "item-1")

        assert item is None


class TestGetDownloadUrl:
    """Tests for get_download_url method."""

    def test_get_download_url_success(self, item_service, dynamodb_stubber, s3_stubber):
        """Test successfully generating download URL for MEDIA item."""
        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure S3 stubber for object existence check
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1024,
                "ETag": '"abc123"',
                "LastModified": datetime(2026, 1, 24, 12, 0, 0),
            },
            {
                "Bucket": "test-bucket",
                "Key": "vaults/vault-123/files/item-1/file.jpg",
            },
        )

        download_url, expires_at, encrypted_metadata, s3_key = item_service.get_download_url(
            "user-123", "vault-123", "item-1"
        )

        assert s3_key == "vaults/vault-123/files/item-1/file.jpg"
        assert encrypted_metadata == b"encrypted-metadata"
        assert expires_at is not None

    def test_get_download_url_item_not_found(self, item_service, dynamodb_stubber):
        """Test download URL when item doesn't exist."""
        # Configure stubber - item not found
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.get_download_url("user-123", "vault-123", "nonexistent")

    def test_get_download_url_unauthorized(self, item_service, dynamodb_stubber):
        """Test download URL when user doesn't own item."""
        # Configure stubber - item owned by different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(ForbiddenError, match="Access denied to item"):
            item_service.get_download_url("user-123", "vault-123", "item-1")

    def test_get_download_url_not_media_type(self, item_service, dynamodb_stubber):
        """Test download URL for non-MEDIA item type."""
        # Configure stubber - item is NOTE type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(BadRequestError, match="Download URL only available for MEDIA items"):
            item_service.get_download_url("user-123", "vault-123", "item-1")

    def test_get_download_url_pending_upload(self, item_service, dynamodb_stubber):
        """Test download URL when upload is still pending."""
        # Configure stubber - item upload is PENDING
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(BadRequestError, match="Item upload not yet complete"):
            item_service.get_download_url("user-123", "vault-123", "item-1")

    def test_get_download_url_s3_object_missing(self, item_service, dynamodb_stubber, s3_stubber):
        """Test download URL when S3 object doesn't exist."""
        # Configure DynamoDB stubber
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure S3 stubber - object doesn't exist
        s3_stubber.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
            http_status_code=404,
        )

        with pytest.raises(InternalServerError, match="Item file not found in storage"):
            item_service.get_download_url("user-123", "vault-123", "item-1")


class TestDeleteItem:
    """Test suite for delete_item method."""

    def test_delete_media_item_success(self, item_service, dynamodb_stubber, s3_stubber):
        """Test successful deletion of MEDIA item with S3 object."""
        # Configure DynamoDB stubber - get_item for MEDIA type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure S3 stubber - delete_object
        s3_stubber.add_response(
            "delete_object",
            {},
            {
                "Bucket": "test-bucket",
                "Key": "vaults/vault-123/files/item-1/file.jpg",
            },
        )

        # Configure DynamoDB stubber - delete_item
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Should not raise any exceptions
        item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_note_item_success(self, item_service, dynamodb_stubber):
        """Test successful deletion of NOTE item (no S3 object)."""
        # Configure DynamoDB stubber - get_item returns None for MEDIA
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure DynamoDB stubber - get_item for NOTE type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#NOTE#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure DynamoDB stubber - delete_item
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Should not raise any exceptions
        item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_item_not_found(self, item_service, dynamodb_stubber):
        """Test deletion when item doesn't exist."""
        # Configure DynamoDB stubber - get_item returns None for all types
        for _ in range(4):  # MEDIA, NOTE, TASK, EVENT
            dynamodb_stubber.add_response(
                "get_item",
                {},
                {
                    "TableName": "test-items-table",
                    "Key": ANY,
                },
            )

        with pytest.raises(NotFoundError, match="Item not found"):
            item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_item_unauthorized(self, item_service, dynamodb_stubber):
        """Test deletion when user doesn't own the item."""
        # Configure DynamoDB stubber - get_item for MEDIA type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        with pytest.raises(ForbiddenError, match="Access denied to item"):
            item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_media_item_pending_upload(self, item_service, dynamodb_stubber, s3_stubber):
        """Test deletion of MEDIA item with pending multipart upload."""
        # Configure DynamoDB stubber - get_item for MEDIA type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure S3 stubber - abort_multipart_upload
        s3_stubber.add_response(
            "abort_multipart_upload",
            {},
            {
                "Bucket": "test-bucket",
                "Key": "vaults/vault-123/files/item-1/file.jpg",
                "UploadId": "test-upload-id",
            },
        )

        # Configure DynamoDB stubber - delete_item
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Should not raise any exceptions
        item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_media_item_s3_failure(self, item_service, dynamodb_stubber, s3_stubber):
        """Test deletion when S3 delete fails."""
        # Configure DynamoDB stubber - get_item for MEDIA type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure S3 stubber - delete_object fails
        s3_stubber.add_client_error(
            "delete_object",
            service_error_code="InternalError",
            service_message="S3 error",
        )

        with pytest.raises(InternalServerError, match="Failed to delete media file"):
            item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_media_item_dynamodb_failure(self, item_service, dynamodb_stubber, s3_stubber):
        """Test deletion when DynamoDB delete fails after S3 delete succeeds."""
        # Configure DynamoDB stubber - get_item for MEDIA type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#MEDIA#item-1"},
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
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure S3 stubber - delete_object succeeds
        s3_stubber.add_response(
            "delete_object",
            {},
            {
                "Bucket": "test-bucket",
                "Key": "vaults/vault-123/files/item-1/file.jpg",
            },
        )

        # Configure DynamoDB stubber - delete_item fails
        dynamodb_stubber.add_client_error(
            "delete_item",
            service_error_code="InternalError",
            service_message="DynamoDB error",
        )

        with pytest.raises(
            InternalServerError,
            match="Failed to delete item metadata - S3 object deleted but metadata remains",
        ):
            item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_task_item_success(self, item_service, dynamodb_stubber):
        """Test successful deletion of TASK item."""
        # Configure DynamoDB stubber - get_item returns None for MEDIA and NOTE
        for _ in range(2):
            dynamodb_stubber.add_response(
                "get_item",
                {},
                {
                    "TableName": "test-items-table",
                    "Key": ANY,
                },
            )

        # Configure DynamoDB stubber - get_item for TASK type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#TASK#item-1"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "TASK"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_content": {"B": b"encrypted-content"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure DynamoDB stubber - delete_item
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Should not raise any exceptions
        item_service.delete_item("user-123", "vault-123", "item-1")

    def test_delete_event_item_success(self, item_service, dynamodb_stubber):
        """Test successful deletion of EVENT item."""
        # Configure DynamoDB stubber - get_item returns None for MEDIA, NOTE, TASK
        for _ in range(3):
            dynamodb_stubber.add_response(
                "get_item",
                {},
                {
                    "TableName": "test-items-table",
                    "Key": ANY,
                },
            )

        # Configure DynamoDB stubber - get_item for EVENT type
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "VAULT#vault-123"},
                    "SK": {"S": "ITEM#EVENT#item-1"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "EVENT"},
                    "vault_id": {"S": "vault-123"},
                    "user_id": {"S": "user-123"},
                    "encrypted_content": {"B": b"encrypted-content"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "version": {"N": "1"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Configure DynamoDB stubber - delete_item
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-items-table",
                "Key": ANY,
            },
        )

        # Should not raise any exceptions
        item_service.delete_item("user-123", "vault-123", "item-1")


class TestDeleteItemErrorHandling:
    """Test error handling in delete_item."""

    def test_delete_item_s3_error_raises_storage_error(self, boto_session):
        """Test that S3 deletion errors are properly raised."""
        from unittest.mock import MagicMock

        service = ItemService(
            session=boto_session,
            items_table_name="test-items",
            s3_bucket_name="test-bucket",
        )

        # Mock get_item to return a MEDIA item
        service.items_repo.get_item = MagicMock(
            return_value={
                "item_id": "item-123",
                "item_type": "MEDIA",
                "vault_id": "vault-123",
                "user_id": "user-123",
                "s3_key": "test-key",
                "upload_status": "COMPLETE",
            }
        )

        # Mock S3 delete to raise an error
        service.s3_repo.delete_object = MagicMock(
            side_effect=InternalServerError("S3 delete failed")
        )

        # Should raise InternalServerError
        with pytest.raises(InternalServerError, match="Failed to delete media file"):
            service.delete_item("user-123", "vault-123", "item-123")
