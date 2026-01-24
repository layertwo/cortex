"""
Unit tests for shared/repository.py module.

Tests DynamoDB and S3 repository operations using botocore stubbers.
"""

import base64
import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

from src.shared.errors import StorageError
from src.shared.repository import (
    DynamoDBRepository,
    S3Repository,
    build_s3_key,
    encode_pagination_token,
    parse_pagination_token,
)


@pytest.fixture
def dynamodb_table_name():
    return "test-table"


@pytest.fixture
def s3_bucket_name():
    return "test-bucket"


class TestDynamoDBRepository:
    """Tests for DynamoDBRepository class."""

    def test_init_with_table_name(self, dynamodb_table_name):
        """Should initialize with table name."""
        with patch.object(boto3, "resource") as mock_resource:
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            repo = DynamoDBRepository(table_name=dynamodb_table_name)

            assert repo.table_name == dynamodb_table_name
            assert repo.table is not None

    def test_init_without_table_name(self):
        """Should initialize without table when name not provided."""
        with patch.object(boto3, "resource") as mock_resource:
            mock_dynamodb = MagicMock()
            mock_resource.return_value = mock_dynamodb

            repo = DynamoDBRepository()

            assert repo.table_name is None
            assert repo.table is None

    def test_get_item_returns_item(self, dynamodb_table_name):
        """Should return item when found."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)

        # Mock the table's get_item method
        repo.table = MagicMock()
        repo.table.get_item.return_value = {
            "Item": {"PK": "USER#123", "SK": "PROFILE", "name": "Test"}
        }

        result = repo.get_item({"PK": "USER#123", "SK": "PROFILE"})

        assert result is not None
        assert result["name"] == "Test"
        repo.table.get_item.assert_called_once_with(Key={"PK": "USER#123", "SK": "PROFILE"})

    def test_get_item_returns_none_when_not_found(self, dynamodb_table_name):
        """Should return None when item not found."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.get_item.return_value = {}

        result = repo.get_item({"PK": "USER#nonexistent", "SK": "PROFILE"})

        assert result is None

    def test_put_item_stores_item(self, dynamodb_table_name):
        """Should store item in DynamoDB."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.put_item.return_value = {}

        repo.put_item({"PK": "USER#456", "SK": "PROFILE", "email": "test@example.com"})

        repo.table.put_item.assert_called_once_with(
            Item={"PK": "USER#456", "SK": "PROFILE", "email": "test@example.com"}
        )

    def test_put_item_with_condition(self, dynamodb_table_name):
        """Should support condition expression."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.put_item.return_value = {}

        repo.put_item(
            {"PK": "USER#789", "SK": "PROFILE", "name": "First"},
            condition_expression="attribute_not_exists(PK)",
        )

        repo.table.put_item.assert_called_once_with(
            Item={"PK": "USER#789", "SK": "PROFILE", "name": "First"},
            ConditionExpression="attribute_not_exists(PK)",
        )

    def test_update_item_updates_attributes(self, dynamodb_table_name):
        """Should update item attributes."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.update_item.return_value = {
            "Attributes": {"PK": "USER#123", "SK": "PROFILE", "count": 5}
        }

        result = repo.update_item(
            key={"PK": "USER#123", "SK": "PROFILE"},
            update_expression="SET #c = :val",
            expression_attribute_values={":val": 5},
            expression_attribute_names={"#c": "count"},
        )

        assert result["count"] == 5
        repo.table.update_item.assert_called_once()

    def test_update_item_without_attribute_names(self, dynamodb_table_name):
        """Should update without expression attribute names."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.update_item.return_value = {"Attributes": {"count": 10}}

        result = repo.update_item(
            key={"PK": "USER#123", "SK": "PROFILE"},
            update_expression="SET count = :val",
            expression_attribute_values={":val": 10},
        )

        assert result["count"] == 10

    def test_delete_item_removes_item(self, dynamodb_table_name):
        """Should delete item from DynamoDB."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.delete_item.return_value = {}

        repo.delete_item({"PK": "USER#123", "SK": "PROFILE"})

        repo.table.delete_item.assert_called_once_with(Key={"PK": "USER#123", "SK": "PROFILE"})

    def test_query_returns_items(self, dynamodb_table_name):
        """Should query items by key condition."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.query.return_value = {
            "Items": [
                {"PK": "VAULT#v1", "SK": "FILE#f1", "name": "file1"},
                {"PK": "VAULT#v1", "SK": "FILE#f2", "name": "file2"},
            ]
        }

        result = repo.query(
            key_condition_expression="PK = :pk", expression_attribute_values={":pk": "VAULT#v1"}
        )

        assert len(result["Items"]) == 2
        assert result["LastEvaluatedKey"] is None

    def test_query_with_limit(self, dynamodb_table_name):
        """Should respect limit parameter."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.query.return_value = {
            "Items": [{"PK": "VAULT#v1", "SK": "FILE#f0"}, {"PK": "VAULT#v1", "SK": "FILE#f1"}],
            "LastEvaluatedKey": {"PK": "VAULT#v1", "SK": "FILE#f1"},
        }

        result = repo.query(
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "VAULT#v1"},
            limit=2,
        )

        assert len(result["Items"]) == 2
        assert result["LastEvaluatedKey"] is not None

    def test_query_descending_order(self, dynamodb_table_name):
        """Should support descending sort order."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.query.return_value = {
            "Items": [
                {"PK": "VAULT#v1", "SK": "FILE#c"},
                {"PK": "VAULT#v1", "SK": "FILE#b"},
                {"PK": "VAULT#v1", "SK": "FILE#a"},
            ]
        }

        result = repo.query(
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "VAULT#v1"},
            scan_index_forward=False,
        )

        assert result["Items"][0]["SK"] == "FILE#c"
        assert result["Items"][2]["SK"] == "FILE#a"

    def test_query_with_index(self, dynamodb_table_name):
        """Should query using GSI."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.query.return_value = {"Items": [{"GSI1PK": "TAG#test"}]}

        result = repo.query(
            key_condition_expression="GSI1PK = :pk",
            expression_attribute_values={":pk": "TAG#test"},
            index_name="GSI1",
        )

        assert len(result["Items"]) == 1
        # Verify IndexName was passed
        call_kwargs = repo.table.query.call_args[1]
        assert call_kwargs["IndexName"] == "GSI1"

    def test_query_with_pagination(self, dynamodb_table_name):
        """Should support pagination with exclusive_start_key."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.query.return_value = {"Items": [{"PK": "V#1", "SK": "F#3"}]}

        start_key = {"PK": "V#1", "SK": "F#2"}
        repo.query(
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "V#1"},
            exclusive_start_key=start_key,
        )

        call_kwargs = repo.table.query.call_args[1]
        assert call_kwargs["ExclusiveStartKey"] == start_key


class TestS3Repository:
    """Tests for S3Repository class."""

    def test_init_with_bucket_name(self, s3_bucket_name):
        """Should initialize with bucket name."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        assert repo.bucket_name == s3_bucket_name

    def test_init_from_env_var(self, monkeypatch, s3_bucket_name):
        """Should initialize from environment variable."""
        monkeypatch.setenv("FILES_BUCKET_NAME", s3_bucket_name)

        repo = S3Repository()

        assert repo.bucket_name == s3_bucket_name

    def test_init_raises_without_bucket(self, monkeypatch):
        """Should raise when bucket name not configured."""
        monkeypatch.delenv("FILES_BUCKET_NAME", raising=False)

        with pytest.raises(ValueError, match="S3 bucket name not configured"):
            S3Repository()

    def test_generate_upload_url(self, s3_bucket_name):
        """Should generate presigned upload URL."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        with Stubber(repo.s3_client):
            # generate_presigned_url doesn't need stubbing - it's client-side only
            url = repo.generate_upload_url(
                object_key="vaults/v1/files/f1/key", content_type="image/jpeg"
            )

        assert s3_bucket_name in url
        assert "vaults" in url

    def test_generate_upload_url_custom_expiration(self, s3_bucket_name):
        """Should accept custom expiration."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        url = repo.generate_upload_url(
            object_key="test-key", content_type="image/png", expiration=3600
        )

        assert s3_bucket_name in url

    def test_generate_download_url(self, s3_bucket_name):
        """Should generate presigned download URL."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        url = repo.generate_download_url(object_key="test-key")

        assert s3_bucket_name in url
        assert "test-key" in url

    def test_generate_download_url_custom_expiration(self, s3_bucket_name):
        """Should accept custom expiration for download."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        url = repo.generate_download_url(object_key="test-key", expiration=1800)

        assert s3_bucket_name in url

    def test_initiate_multipart_upload(self, s3_bucket_name):
        """Should initiate multipart upload."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        with Stubber(repo.s3_client) as stubber:
            stubber.add_response(
                "create_multipart_upload",
                {"UploadId": "test-upload-id-123"},
                {
                    "Bucket": s3_bucket_name,
                    "Key": "large-file",
                    "ContentType": "video/mp4",
                    "ServerSideEncryption": "AES256",
                },
            )

            upload_id = repo.initiate_multipart_upload(
                object_key="large-file", content_type="video/mp4"
            )

        assert upload_id == "test-upload-id-123"

    def test_generate_multipart_upload_url(self, s3_bucket_name):
        """Should generate URL for multipart upload part."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        url = repo.generate_multipart_upload_url(
            object_key="large-file",
            content_type="video/mp4",
            part_number=1,
            upload_id="test-upload-id",
        )

        assert s3_bucket_name in url

    def test_delete_object(self, s3_bucket_name):
        """Should delete object from S3."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        with Stubber(repo.s3_client) as stubber:
            stubber.add_response(
                "delete_object", {}, {"Bucket": s3_bucket_name, "Key": "to-delete"}
            )

            repo.delete_object(object_key="to-delete")

    def test_object_exists_returns_true(self, s3_bucket_name):
        """Should return True when object exists."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        with Stubber(repo.s3_client) as stubber:
            stubber.add_response(
                "head_object",
                {"ContentLength": 100, "ContentType": "image/jpeg"},
                {"Bucket": s3_bucket_name, "Key": "existing"},
            )

            result = repo.object_exists(object_key="existing")

        assert result is True

    def test_object_exists_returns_false(self, s3_bucket_name):
        """Should return False when object doesn't exist."""
        repo = S3Repository(bucket_name=s3_bucket_name)

        with Stubber(repo.s3_client) as stubber:
            stubber.add_client_error(
                "head_object",
                service_error_code="404",
                service_message="Not Found",
                expected_params={"Bucket": s3_bucket_name, "Key": "nonexistent"},
            )

            result = repo.object_exists(object_key="nonexistent")

        assert result is False


class TestBuildS3Key:
    """Tests for build_s3_key function."""

    def test_builds_key_with_correct_format(self):
        """Should build key with correct format."""
        key = build_s3_key("vault-123", "file-456")

        assert key.startswith("vaults/vault-123/files/file-456/")
        parts = key.split("/")
        assert len(parts) == 5
        assert "-" in parts[4]

    def test_builds_unique_keys(self):
        """Should build unique keys for same inputs."""
        key1 = build_s3_key("vault-123", "file-456")
        key2 = build_s3_key("vault-123", "file-456")

        assert key1 != key2

    def test_includes_vault_and_file_ids(self):
        """Should include vault and file IDs in path."""
        key = build_s3_key("my-vault", "my-file")

        assert "my-vault" in key
        assert "my-file" in key


class TestParsePaginationToken:
    """Tests for parse_pagination_token function."""

    def test_parses_valid_token(self):
        """Should parse valid base64-encoded token."""
        original = {"PK": "VAULT#v1", "SK": "FILE#f1"}
        token = base64.b64encode(json.dumps(original).encode()).decode()

        result = parse_pagination_token(token)

        assert result == original

    def test_returns_none_for_none_input(self):
        """Should return None for None input."""
        result = parse_pagination_token(None)

        assert result is None

    def test_returns_none_for_empty_string(self):
        """Should return None for empty string."""
        result = parse_pagination_token("")

        assert result is None

    def test_returns_none_for_invalid_base64(self):
        """Should return None for invalid base64."""
        result = parse_pagination_token("not-valid-base64!!!")

        assert result is None

    def test_returns_none_for_invalid_json(self):
        """Should return None for invalid JSON."""
        token = base64.b64encode(b"not json").decode()

        result = parse_pagination_token(token)

        assert result is None


class TestEncodePaginationToken:
    """Tests for encode_pagination_token function."""

    def test_encodes_valid_key(self):
        """Should encode LastEvaluatedKey as base64."""
        key = {"PK": "VAULT#v1", "SK": "FILE#f1"}

        token = encode_pagination_token(key)

        decoded = json.loads(base64.b64decode(token))
        assert decoded == key

    def test_returns_none_for_none_input(self):
        """Should return None for None input."""
        result = encode_pagination_token(None)

        assert result is None

    def test_returns_none_for_empty_dict(self):
        """Should return None for empty dict."""
        result = encode_pagination_token({})

        assert result is None

    def test_roundtrip(self):
        """Should support encode/decode roundtrip."""
        original = {"PK": "USER#123", "SK": "VAULT#456", "extra": "data"}

        token = encode_pagination_token(original)
        decoded = parse_pagination_token(token)

        assert decoded == original


class TestDynamoDBRepositoryErrors:
    """Tests for DynamoDB error handling."""

    def test_get_item_raises_storage_error(self, dynamodb_table_name):
        """Should raise StorageError on DynamoDB failure."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "GetItem"
        )

        with pytest.raises(StorageError):
            repo.get_item({"PK": "test", "SK": "test"})

    def test_put_item_raises_storage_error(self, dynamodb_table_name):
        """Should raise StorageError on put failure."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "PutItem"
        )

        with pytest.raises(StorageError):
            repo.put_item({"PK": "test", "SK": "test"})

    def test_update_item_raises_storage_error(self, dynamodb_table_name):
        """Should raise StorageError on update failure."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.update_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "UpdateItem"
        )

        with pytest.raises(StorageError):
            repo.update_item(
                key={"PK": "test", "SK": "test"},
                update_expression="SET #a = :v",
                expression_attribute_values={":v": 1},
            )

    def test_delete_item_raises_storage_error(self, dynamodb_table_name):
        """Should raise StorageError on delete failure."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.delete_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "DeleteItem"
        )

        with pytest.raises(StorageError):
            repo.delete_item({"PK": "test", "SK": "test"})

    def test_query_raises_storage_error(self, dynamodb_table_name):
        """Should raise StorageError on query failure."""
        with patch.object(boto3, "resource"):
            repo = DynamoDBRepository(table_name=dynamodb_table_name)
        repo.table = MagicMock()
        repo.table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "Query"
        )

        with pytest.raises(StorageError):
            repo.query(
                key_condition_expression="PK = :pk", expression_attribute_values={":pk": "test"}
            )


class TestS3RepositoryErrors:
    """Tests for S3 error handling."""

    def test_generate_upload_url_raises_storage_error(self, s3_bucket_name):
        """Should raise StorageError on URL generation failure."""
        repo = S3Repository(bucket_name=s3_bucket_name)
        repo.s3_client = MagicMock()
        repo.s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}},
            "GeneratePresignedUrl",
        )

        with pytest.raises(StorageError):
            repo.generate_upload_url("key", "image/jpeg")

    def test_generate_download_url_raises_storage_error(self, s3_bucket_name):
        """Should raise StorageError on download URL failure."""
        repo = S3Repository(bucket_name=s3_bucket_name)
        repo.s3_client = MagicMock()
        repo.s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}},
            "GeneratePresignedUrl",
        )

        with pytest.raises(StorageError):
            repo.generate_download_url("key")

    def test_initiate_multipart_raises_storage_error(self, s3_bucket_name):
        """Should raise StorageError on multipart init failure."""
        repo = S3Repository(bucket_name=s3_bucket_name)
        repo.s3_client = MagicMock()
        repo.s3_client.create_multipart_upload.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}},
            "CreateMultipartUpload",
        )

        with pytest.raises(StorageError):
            repo.initiate_multipart_upload("key", "video/mp4")

    def test_delete_object_raises_storage_error(self, s3_bucket_name):
        """Should raise StorageError on delete failure."""
        repo = S3Repository(bucket_name=s3_bucket_name)
        repo.s3_client = MagicMock()
        repo.s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "DeleteObject"
        )

        with pytest.raises(StorageError):
            repo.delete_object("key")

    def test_object_exists_raises_storage_error_on_non_404(self, s3_bucket_name):
        """Should raise StorageError on non-404 errors."""
        repo = S3Repository(bucket_name=s3_bucket_name)
        repo.s3_client = MagicMock()
        repo.s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}}, "HeadObject"
        )

        with pytest.raises(StorageError):
            repo.object_exists("key")

    def test_generate_multipart_url_raises_storage_error(self, s3_bucket_name):
        """Should raise StorageError on multipart URL failure."""
        repo = S3Repository(bucket_name=s3_bucket_name)
        repo.s3_client = MagicMock()
        repo.s3_client.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Test error"}},
            "GeneratePresignedUrl",
        )

        with pytest.raises(StorageError):
            repo.generate_multipart_upload_url("key", "video/mp4", 1, "upload-id")
