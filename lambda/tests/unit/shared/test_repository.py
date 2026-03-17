"""
Unit tests for shared/repository.py module.

Tests DynamoDB and S3 repository operations using botocore stubbers.
"""

import base64
import json

import pytest

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


@pytest.fixture
def dynamodb_repository(boto_session, dynamodb_table_name):
    return DynamoDBRepository(session=boto_session, table_name=dynamodb_table_name)


@pytest.fixture
def s3_repository(boto_session, s3_bucket_name):
    return S3Repository(session=boto_session, bucket_name=s3_bucket_name)


class TestDynamoDBRepository:
    """Tests for DynamoDBRepository class."""

    def test_get_item_returns_item(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should return item when found."""

        dynamodb_stubber.add_response(
            "get_item",
            {"Item": {"name": {"S": "Test"}}},
            {
                "Key": {"PK": "USER#123", "SK": "PROFILE"},
                "TableName": dynamodb_table_name,
            },
        )
        result = dynamodb_repository.get_item({"PK": "USER#123", "SK": "PROFILE"})

        assert result is not None
        assert result["name"] == "Test"

    def test_get_item_returns_none_when_not_found(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should return None when item not found."""
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "Key": {"PK": "USER#nonexistent", "SK": "PROFILE"},
                "TableName": dynamodb_table_name,
            },
        )
        result = dynamodb_repository.get_item({"PK": "USER#nonexistent", "SK": "PROFILE"})

        assert result is None

    def test_put_item_stores_item(self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name):
        """Should store item in DynamoDB."""
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "Item": {"PK": "USER#456", "SK": "PROFILE", "email": "test@example.com"},
                "TableName": dynamodb_table_name,
            },
        )
        dynamodb_repository.put_item(
            {"PK": "USER#456", "SK": "PROFILE", "email": "test@example.com"}
        )

    def test_put_item_with_condition(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should support condition expression."""
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "ConditionExpression": "attribute_not_exists(PK)",
                "Item": {"PK": "USER#789", "SK": "PROFILE", "name": "First"},
                "TableName": dynamodb_table_name,
            },
        )

        dynamodb_repository.put_item(
            {"PK": "USER#789", "SK": "PROFILE", "name": "First"},
            condition_expression="attribute_not_exists(PK)",
        )

    def test_update_item_updates_attributes(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should update item attributes."""
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {"count": {"N": "5"}},
            },
            {
                "Key": {"PK": "USER#123", "SK": "PROFILE"},
                "UpdateExpression": "SET #c = :val",
                "ExpressionAttributeNames": {"#c": "count"},
                "ExpressionAttributeValues": {":val": 5},
                "ReturnValues": "ALL_NEW",
                "TableName": dynamodb_table_name,
            },
        )
        result = dynamodb_repository.update_item(
            key={"PK": "USER#123", "SK": "PROFILE"},
            update_expression="SET #c = :val",
            expression_attribute_values={":val": 5},
            expression_attribute_names={"#c": "count"},
        )

        assert result["count"] == 5

    def test_update_item_without_attribute_names(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should update without expression attribute names."""
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {"count": {"N": "10"}},
            },
            {
                "Key": {"PK": "USER#123", "SK": "PROFILE"},
                "UpdateExpression": "SET count = :val",
                "ExpressionAttributeValues": {":val": 10},
                "ReturnValues": "ALL_NEW",
                "TableName": dynamodb_table_name,
            },
        )
        result = dynamodb_repository.update_item(
            key={"PK": "USER#123", "SK": "PROFILE"},
            update_expression="SET count = :val",
            expression_attribute_values={":val": 10},
        )

        assert result["count"] == 10

    def test_update_item_conditional_success(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should update item with condition expression."""
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {"status": {"S": "COMPLETE"}},
            },
            {
                "Key": {"PK": "VAULT#v1", "SK": "ITEM#i1"},
                "UpdateExpression": "SET #status = :complete",
                "ConditionExpression": "#status = :pending",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {":complete": "COMPLETE", ":pending": "PENDING"},
                "ReturnValues": "ALL_NEW",
                "TableName": dynamodb_table_name,
            },
        )
        result = dynamodb_repository.update_item_conditional(
            key={"PK": "VAULT#v1", "SK": "ITEM#i1"},
            update_expression="SET #status = :complete",
            condition_expression="#status = :pending",
            expression_attribute_values={":complete": "COMPLETE", ":pending": "PENDING"},
            expression_attribute_names={"#status": "status"},
        )

        assert result["status"] == "COMPLETE"

    def test_delete_item_removes_item(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should delete item from DynamoDB."""
        key = {"PK": "USER#123", "SK": "PROFILE"}
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "Key": key,
                "TableName": dynamodb_table_name,
            },
        )
        dynamodb_repository.delete_item(key=key)

    def test_query_returns_items(self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name):
        """Should query items by key condition."""
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#f1"}, "name": {"S": "file1"}},
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#f2"}, "name": {"S": "file2"}},
                ],
            },
            {
                "ExpressionAttributeValues": {":pk": "VAULT#v1"},
                "KeyConditionExpression": "PK = :pk",
                "ScanIndexForward": True,
                "TableName": dynamodb_table_name,
            },
        )

        result = dynamodb_repository.query(
            key_condition_expression="PK = :pk", expression_attribute_values={":pk": "VAULT#v1"}
        )

        assert len(result["Items"]) == 2
        assert result["LastEvaluatedKey"] is None

    def test_query_with_limit(self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name):
        """Should respect limit parameter."""
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#f0"}},
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#f1"}},
                ],
                "LastEvaluatedKey": {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#f1"}},
            },
            {
                "ExpressionAttributeValues": {":pk": "VAULT#v1"},
                "KeyConditionExpression": "PK = :pk",
                "ScanIndexForward": True,
                "TableName": dynamodb_table_name,
                "Limit": 2,
            },
        )

        result = dynamodb_repository.query(
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "VAULT#v1"},
            limit=2,
        )

        assert len(result["Items"]) == 2
        assert result["LastEvaluatedKey"] is not None

    def test_query_descending_order(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should support descending sort order."""
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#c"}},
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#b"}},
                    {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#a"}},
                ],
                "LastEvaluatedKey": {"PK": {"S": "VAULT#v1"}, "SK": {"S": "FILE#a"}},
            },
            {
                "ExpressionAttributeValues": {":pk": "VAULT#v1"},
                "KeyConditionExpression": "PK = :pk",
                "ScanIndexForward": False,
                "TableName": dynamodb_table_name,
            },
        )

        result = dynamodb_repository.query(
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "VAULT#v1"},
            scan_index_forward=False,
        )

        assert result["Items"][0]["SK"] == "FILE#c"
        assert result["Items"][2]["SK"] == "FILE#a"

    def test_query_with_index(self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name):
        """Should query using GSI."""

        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {"PK": {"S": "TAG#v1"}},
                ],
            },
            {
                "ExpressionAttributeValues": {":pk": "TAG#test"},
                "IndexName": "GSI1",
                "KeyConditionExpression": "GSI1PK = :pk",
                "ScanIndexForward": True,
                "TableName": dynamodb_table_name,
            },
        )

        result = dynamodb_repository.query(
            key_condition_expression="GSI1PK = :pk",
            expression_attribute_values={":pk": "TAG#test"},
            index_name="GSI1",
        )

        assert len(result["Items"]) == 1

    def test_query_with_pagination(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should support pagination with exclusive_start_key."""
        start_key = {"PK": "V#1", "SK": "F#2"}

        dynamodb_stubber.add_response(
            "query",
            {},
            {
                "ExclusiveStartKey": start_key,
                "ExpressionAttributeValues": {":pk": "V#1"},
                "KeyConditionExpression": "PK = :pk",
                "ScanIndexForward": True,
                "TableName": dynamodb_table_name,
            },
        )

        dynamodb_repository.query(
            key_condition_expression="PK = :pk",
            expression_attribute_values={":pk": "V#1"},
            exclusive_start_key=start_key,
        )

    def test_transact_write_items(self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name):
        """Should write multiple items atomically."""
        items = [
            {
                "Put": {
                    "TableName": dynamodb_table_name,
                    "Item": {"PK": {"S": "A"}, "SK": {"S": "1"}},
                }
            },
            {
                "Put": {
                    "TableName": dynamodb_table_name,
                    "Item": {"PK": {"S": "B"}, "SK": {"S": "2"}},
                }
            },
        ]
        dynamodb_stubber.add_response(
            "transact_write_items",
            {},
            {"TransactItems": items},
        )
        dynamodb_repository.transact_write_items(items)

    def test_batch_get_items(self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name):
        """Should batch get multiple items by keys."""
        keys = [
            {"PK": "ITEM#1", "SK": "METADATA"},
            {"PK": "ITEM#2", "SK": "METADATA"},
        ]
        dynamodb_stubber.add_response(
            "batch_get_item",
            {
                "Responses": {
                    dynamodb_table_name: [
                        {"PK": {"S": "ITEM#1"}, "SK": {"S": "METADATA"}, "item_id": {"S": "1"}},
                        {"PK": {"S": "ITEM#2"}, "SK": {"S": "METADATA"}, "item_id": {"S": "2"}},
                    ]
                },
                "UnprocessedKeys": {},
            },
            {"RequestItems": {dynamodb_table_name: {"Keys": keys}}},
        )
        result = dynamodb_repository.batch_get_items(keys)
        assert len(result) == 2

    def test_batch_get_items_empty_keys(self, dynamodb_repository):
        """Should return empty list for empty keys."""
        result = dynamodb_repository.batch_get_items([])
        assert result == []


class TestS3Repository:
    """Tests for S3Repository class."""

    def test_generate_upload_url(self, s3_repository, s3_bucket_name):
        """Should generate presigned upload URL."""
        # generate_presigned_url doesn't need stubbing - it's client-side only
        url = s3_repository.generate_upload_url(
            object_key="vaults/v1/files/f1/key", content_type="image/jpeg"
        )

        assert s3_bucket_name in url
        assert "vaults" in url

    def test_generate_upload_url_custom_expiration(self, s3_repository, s3_bucket_name):
        """Should accept custom expiration."""
        url = s3_repository.generate_upload_url(
            object_key="test-key", content_type="image/png", expiration=3600
        )

        assert s3_bucket_name in url

    def test_generate_download_url(self, s3_repository, s3_bucket_name):
        """Should generate presigned download URL."""
        url = s3_repository.generate_download_url(object_key="test-key")

        assert s3_bucket_name in url
        assert "test-key" in url

    def test_generate_download_url_custom_expiration(self, s3_repository, s3_bucket_name):
        """Should accept custom expiration for download."""
        url = s3_repository.generate_download_url(object_key="test-key", expiration=1800)

        assert s3_bucket_name in url

    def test_initiate_multipart_upload(self, s3_repository, s3_stubber, s3_bucket_name, s3_client):
        """Should initiate multipart upload."""
        s3_stubber.add_response(
            "create_multipart_upload",
            {"UploadId": "test-upload-id-123"},
            {
                "Bucket": s3_bucket_name,
                "Key": "large-file",
                "ContentType": "video/mp4",
                "ServerSideEncryption": "AES256",
            },
        )

        upload_id = s3_repository.initiate_multipart_upload(
            object_key="large-file", content_type="video/mp4"
        )

        assert upload_id == "test-upload-id-123"

    def test_generate_multipart_upload_url(self, s3_repository, s3_bucket_name):
        """Should generate URL for multipart upload part."""
        url = s3_repository.generate_multipart_upload_url(
            object_key="large-file",
            content_type="video/mp4",
            part_number=1,
            upload_id="test-upload-id",
        )

        assert s3_bucket_name in url

    def test_delete_object(self, s3_repository, s3_stubber, s3_bucket_name, s3_client):
        """Should delete object from S3."""
        s3_stubber.add_response("delete_object", {}, {"Bucket": s3_bucket_name, "Key": "to-delete"})

        s3_repository.delete_object(object_key="to-delete")

    def test_object_exists_returns_true(self, s3_repository, s3_stubber, s3_bucket_name, s3_client):
        """Should return True when object exists."""
        s3_stubber.add_response(
            "head_object",
            {"ContentLength": 100, "ContentType": "image/jpeg"},
            {"Bucket": s3_bucket_name, "Key": "existing"},
        )

        result = s3_repository.object_exists(object_key="existing")

        assert result is True

    def test_object_exists_returns_false(
        self, s3_repository, s3_stubber, s3_bucket_name, s3_client
    ):
        """Should return False when object doesn't exist."""

        s3_stubber.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
            expected_params={"Bucket": s3_bucket_name, "Key": "nonexistent"},
        )

        result = s3_repository.object_exists(object_key="nonexistent")

        assert result is False

    def test_get_object_metadata_returns_metadata(
        self, s3_repository, s3_stubber, s3_bucket_name, s3_client
    ):
        """Should return object metadata including version ID."""
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1024,
                "ContentType": "image/jpeg",
                "ETag": '"abc123"',
                "LastModified": "2024-01-24T12:00:00Z",
                "VersionId": "version-abc123",
            },
            {"Bucket": s3_bucket_name, "Key": "test-key"},
        )

        metadata = s3_repository.get_object_metadata(object_key="test-key")

        assert metadata is not None
        assert metadata["content_length"] == 1024
        assert metadata["etag"] == '"abc123"'
        assert metadata["version_id"] == "version-abc123"

    def test_get_object_metadata_without_version_id(
        self, s3_repository, s3_stubber, s3_bucket_name, s3_client
    ):
        """Should return metadata without version ID for non-versioned buckets."""
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 2048,
                "ContentType": "video/mp4",
                "ETag": '"def456"',
                "LastModified": "2024-01-24T12:00:00Z",
            },
            {"Bucket": s3_bucket_name, "Key": "test-key"},
        )

        metadata = s3_repository.get_object_metadata(object_key="test-key")

        assert metadata is not None
        assert metadata["content_length"] == 2048
        assert "version_id" not in metadata

    def test_get_object_metadata_returns_none_for_404(
        self, s3_repository, s3_stubber, s3_bucket_name, s3_client
    ):
        """Should return None when object doesn't exist."""
        s3_stubber.add_client_error(
            "head_object",
            service_error_code="404",
            service_message="Not Found",
            expected_params={"Bucket": s3_bucket_name, "Key": "nonexistent"},
        )

        metadata = s3_repository.get_object_metadata(object_key="nonexistent")

        assert metadata is None

    def test_abort_multipart_upload(self, s3_repository, s3_stubber, s3_bucket_name, s3_client):
        """Should abort multipart upload and clean up parts."""
        s3_stubber.add_response(
            "abort_multipart_upload",
            {},
            {
                "Bucket": s3_bucket_name,
                "Key": "large-file",
                "UploadId": "test-upload-id-123",
            },
        )

        s3_repository.abort_multipart_upload(
            object_key="large-file", upload_id="test-upload-id-123"
        )


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
        assert token is not None

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


class TestUpdateItemConditionalWithAttributeNames:
    """Test update_item_conditional with expression attribute names."""

    def test_update_item_conditional_with_attribute_names(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should support expression attribute names in conditional update."""
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"status": {"S": "ACTIVE"}}},
            {
                "Key": {"PK": "test", "SK": "test"},
                "UpdateExpression": "SET #s = :val",
                "ConditionExpression": "#s = :old",
                "ExpressionAttributeNames": {"#s": "status"},
                "ExpressionAttributeValues": {":val": "ACTIVE", ":old": "PENDING"},
                "ReturnValues": "ALL_NEW",
                "TableName": dynamodb_table_name,
            },
        )

        result = dynamodb_repository.update_item_conditional(
            key={"PK": "test", "SK": "test"},
            update_expression="SET #s = :val",
            condition_expression="#s = :old",
            expression_attribute_values={":val": "ACTIVE", ":old": "PENDING"},
            expression_attribute_names={"#s": "status"},
        )

        assert result["status"] == "ACTIVE"

    def test_update_item_conditional_without_attribute_names(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should work without expression attribute names."""
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"count": {"N": "5"}}},
            {
                "Key": {"PK": "test", "SK": "test"},
                "UpdateExpression": "SET count = :val",
                "ConditionExpression": "count = :old",
                "ExpressionAttributeValues": {":val": 5, ":old": 4},
                "ReturnValues": "ALL_NEW",
                "TableName": dynamodb_table_name,
            },
        )

        result = dynamodb_repository.update_item_conditional(
            key={"PK": "test", "SK": "test"},
            update_expression="SET count = :val",
            condition_expression="count = :old",
            expression_attribute_values={":val": 5, ":old": 4},
        )

        assert result["count"] == 5


class TestQueryWithAttributeNames:
    """Test query with expression attribute names."""

    def test_query_with_expression_attribute_names(
        self, dynamodb_repository, dynamodb_stubber, dynamodb_table_name
    ):
        """Should support expression attribute names in query."""
        dynamodb_stubber.add_response(
            "query",
            {"Items": [{"PK": {"S": "test"}, "SK": {"S": "test"}}]},
            {
                "ExpressionAttributeNames": {"#pk": "PK"},
                "ExpressionAttributeValues": {":pk": "test"},
                "KeyConditionExpression": "#pk = :pk",
                "ScanIndexForward": True,
                "TableName": dynamodb_table_name,
            },
        )

        result = dynamodb_repository.query(
            key_condition_expression="#pk = :pk",
            expression_attribute_values={":pk": "test"},
            expression_attribute_names={"#pk": "PK"},
        )

        assert len(result["Items"]) == 1
