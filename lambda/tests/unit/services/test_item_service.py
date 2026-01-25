"""
Unit tests for ItemService.

Tests the item service layer for creating items, initiating uploads,
and completing uploads for all item types.
"""

import uuid
from datetime import datetime

import pytest
from botocore.stub import ANY

from src.api.services.item_service import ItemService
from src.shared.errors import AuthorizationError, ResourceNotFoundError, StorageError
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

        # Execute with stubbers
        with s3_stubber, dynamodb_stubber:
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
                    "updated_at": {"N": str(int(datetime.utcnow().timestamp()))},
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

        with pytest.raises(ResourceNotFoundError):
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

        with pytest.raises(AuthorizationError):
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

        with pytest.raises(StorageError, match="Upload verification failed"):
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

        with pytest.raises(StorageError, match="Upload verification failed"):
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

        with pytest.raises(StorageError, match="object was deleted during completion"):
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
                    "updated_at": {"N": str(int(datetime.utcnow().timestamp()))},
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

        # Execute with stubbers
        with s3_stubber, dynamodb_stubber:
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

        # Execute with stubbers
        with s3_stubber, dynamodb_stubber:
            item_service.cleanup_failed_upload("vault-123", item_id, s3_key, upload_id)
