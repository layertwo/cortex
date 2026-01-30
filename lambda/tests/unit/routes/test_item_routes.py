"""
Unit tests for item route handlers.

Tests verify that item routes work correctly through the lambda handler entrypoint.
"""

import json
from datetime import datetime, timezone

import pytest
from botocore.stub import ANY

from src.entrypoint.api import lambda_handler


class TestCreateItemRoute:
    """Test suite for CreateItemRoute through lambda handler."""

    def test_create_item_route_handler(self, mock_service_provider, dynamodb_stubber):
        """Test create item route handler returns expected response."""
        user_id = "test-user-123"
        vault_id = "test-vault-456"

        # Stub DynamoDB put_item call
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_id": vault_id,
                    "item_type": "NOTE",
                    "encrypted_content": "ZW5jcnlwdGVkLWNvbnRlbnQ=",
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify the response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Validate response structure
        assert "item_id" in body, "Response should include item_id"
        assert "item_type" in body, "Response should include item_type"
        assert "created_at" in body, "Response should include created_at"

        # Validate response values
        assert isinstance(body["item_id"], str), "item_id should be a string"
        assert len(body["item_id"]) > 0, "item_id should not be empty"
        assert body["item_type"] == "NOTE", f"item_type should be NOTE, got {body['item_type']}"

        # Validate created_at is ISO format datetime string
        try:
            datetime.fromisoformat(body["created_at"])
        except ValueError:
            pytest.fail(f"created_at should be ISO format datetime, got {body['created_at']}")


class TestInitiateUploadRoute:
    """Test suite for InitiateUploadRoute through lambda handler."""

    def test_initiate_upload_route_handler(self, mock_service_provider, dynamodb_stubber):
        """Test initiate upload route handler returns expected response."""
        user_id = "test-user-123"
        vault_id = "test-vault-456"

        # Stub DynamoDB put_item call (creates item metadata)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        event = {
            "resource": "/v1/items/upload/init",
            "path": "/v1/items/upload/init",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_id": vault_id,
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                    "size_bytes": 50 * 1024 * 1024,  # 50MB - small file
                    "content_type": "image/jpeg",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify the response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Validate response structure
        assert "item_id" in body, "Response should include item_id"
        assert "upload_url" in body, "Response should include upload_url"
        assert "expires_at" in body, "Response should include expires_at"
        assert "s3_key" in body, "Response should include s3_key"
        assert "upload_id" in body, "Response should include upload_id"

        # Validate response values
        assert isinstance(body["item_id"], str), "item_id should be a string"
        assert len(body["item_id"]) > 0, "item_id should not be empty"

        assert isinstance(body["upload_url"], str), "upload_url should be a string"
        assert body["upload_url"].startswith("https://"), "upload_url should be HTTPS"

        assert isinstance(body["s3_key"], str), "s3_key should be a string"
        assert vault_id in body["s3_key"], f"s3_key should contain vault_id {vault_id}"
        assert body["item_id"] in body["s3_key"], "s3_key should contain item_id"

        # Validate expires_at is ISO format datetime string
        try:
            datetime.fromisoformat(body["expires_at"])
        except ValueError:
            pytest.fail(f"expires_at should be ISO format datetime, got {body['expires_at']}")

        # For small files (<100MB), upload_id should be None (no multipart)
        assert body["upload_id"] is None, "upload_id should be None for small files"


class TestCompleteUploadRoute:
    """Test suite for CompleteUploadRoute through lambda handler."""

    def test_complete_upload_route_handler(
        self, mock_service_provider, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test complete upload route handler returns expected response."""
        user_id = "test-user-123"
        vault_id = "test-vault-456"
        item_id = "test-item-789"
        s3_key = f"vaults/{vault_id}/files/{item_id}/test"

        # Stub DynamoDB get_item call (retrieve item metadata)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": vault_id},
                    "s3_key": {"S": s3_key},
                    "upload_status": {"S": "PENDING"},
                }
            },
            expected_params={
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"ITEM#{item_id}",
                },
            },
        )

        # Stub S3 head_object call (verify file exists)
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1000,
                "ContentType": "image/jpeg",
            },
            {
                "Bucket": files_bucket_name,
                "Key": s3_key,
            },
        )

        # Stub DynamoDB update_item call (mark upload complete)
        now_timestamp = int(datetime.now(tz=timezone.utc).timestamp())
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "upload_status": {"S": "COMPLETE"},
                    "updated_at": {"N": str(now_timestamp)},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"ITEM#{item_id}",
                },
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        event = {
            "resource": "/v1/items/upload/complete",
            "path": "/v1/items/upload/complete",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "item_id": item_id,
                    "vault_id": vault_id,
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify the response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # Validate response structure
        assert "item_id" in body, "Response should include item_id"
        assert "uploaded_at" in body, "Response should include uploaded_at"

        # Validate response values
        assert body["item_id"] == item_id, f"item_id should be {item_id}, got {body['item_id']}"

        # Validate uploaded_at is ISO format datetime string
        try:
            uploaded_at = datetime.fromisoformat(body["uploaded_at"])
            # Ensure the timestamp is recent (within last minute)
            now = datetime.now(tz=timezone.utc)
            time_diff = abs((now - uploaded_at.replace(tzinfo=timezone.utc)).total_seconds())
            assert (
                time_diff < 60
            ), f"uploaded_at timestamp should be recent, got {body['uploaded_at']}"
        except ValueError:
            pytest.fail(f"uploaded_at should be ISO format datetime, got {body['uploaded_at']}")


class TestListItemsRoute:
    """Test suite for ListItemsRoute through lambda handler."""

    def test_list_items_route_handler_missing_vault_id(self, mock_service_provider):
        """Test list items route handler returns error when vault_id is missing."""
        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 because vault_id is required
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "vault_id is required"}
        assert body["statusCode"] == 400
        assert "vault_id is required" in body["message"]

    def test_list_items_route_handler_with_vault_id(
        self, mock_service_provider, dynamodb_stubber, vaults_table_name, items_table_name
    ):
        """Test list items route handler with vault_id returns empty list for empty vault."""
        user_id = "test-user-123"
        vault_id = "vault-123"

        # Stub DynamoDB get_item call for vault_exists check
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                }
            },
            expected_params={
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        # Stub DynamoDB query call for list_items - empty vault
        # Query uses GSI2 (listing all items without type filter)
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            expected_params={
                "TableName": items_table_name,
                "IndexName": "GSI2",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": ANY,
                "ScanIndexForward": ANY,
                "Limit": ANY,
            },
        )

        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)
        body = json.loads(response["body"])

        # Empty vault owned by user returns empty list (valid case)
        assert response["statusCode"] == 200
        assert body["items"] == []

    def test_list_items_returns_404_for_nonexistent_vault(
        self, mock_service_provider, dynamodb_stubber, vaults_table_name
    ):
        """
        Test that list items returns 404 when vault doesn't exist.

        Security requirement: Prevents vault enumeration by returning the same
        response for non-existent vaults as for unauthorized access.
        """
        user_id = "test-user-123"
        vault_id = "nonexistent-vault"

        # Stub DynamoDB get_item call for vault_exists - vault not found
        dynamodb_stubber.add_response(
            "get_item",
            {},  # Empty response means vault not found
            expected_params={
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Non-existent vault returns 404, NOT empty list
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["statusCode"] == 404
        assert "Vault not found" in body["message"]

    def test_list_items_returns_404_for_vault_owned_by_different_user(
        self, mock_service_provider, dynamodb_stubber, vaults_table_name
    ):
        """
        Test that list items returns 404 when vault exists but belongs to different user.

        Security requirement: Prevents vault enumeration by returning 404 for both
        'vault doesn't exist' and 'vault exists but unauthorized'. Attackers cannot
        distinguish valid vault IDs from invalid ones.
        """
        user_id = "test-user-123"
        vault_id = "vault-owned-by-other-user"

        # Stub DynamoDB get_item call for vault_exists - vault not found for THIS user
        # The vault exists for different_user_id but not for user_id
        # vault_exists queries with USER#{user_id} so vault won't be found
        dynamodb_stubber.add_response(
            "get_item",
            {},  # Empty response - vault exists but not owned by this user
            expected_params={
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Vault owned by different user returns 404, NOT empty list
        # This prevents vault enumeration attacks
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["statusCode"] == 404
        assert "Vault not found" in body["message"]


class TestGetItemRoute:
    """Test suite for GetItemRoute through lambda handler."""

    def test_get_item_route_handler(
        self, mock_service_provider, dynamodb_stubber, items_table_name
    ):
        """Test get item route handler with vault_id."""
        user_id = "test-user-123"
        vault_id = "vault-123"
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "queryStringParameters": {},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }
        now_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "user_id": {"S": user_id},
                    "item_id": {"S": item_id},
                    "item_type": {"S": "event"},
                    "vault_id": {"S": vault_id},
                    "encrypted_metadata": {"B": "foobar".encode()},
                    "created_at": {"N": now_timestamp},
                    "updated_at": {"N": now_timestamp},
                }
            },
            expected_params={
                "Key": {"PK": "ITEM#test-item-123"},
                "TableName": items_table_name,
            },
        )

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["item_id"] == item_id
        assert body["item_type"] == "event"
        assert body["vault_id"] == vault_id
        assert body["encrypted_metadata"] == "foobar"
        assert "created_at" in body
        assert "updated_at" in body


class TestUpdateItemRoute:
    """Test suite for UpdateItemRoute through lambda handler."""

    def test_update_item_route_handler(self, mock_service_provider):
        """Test update item route handler returns expected response."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "PUT",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Update item endpoint" in body["message"]


class TestDeleteItemRoute:
    """Test suite for DeleteItemRoute through lambda handler."""

    def test_delete_item_route_handler(
        self, mock_service_provider, dynamodb_stubber, items_table_name
    ):
        """Test delete item route handler successfully deletes an item."""
        user_id = "test-user-123"
        item_id = "test-item-123"
        vault_id = "test-vault-456"

        # Stub DynamoDB get_item call (retrieve item to verify ownership)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": vault_id},
                    "item_type": {"S": "NOTE"},
                    "encrypted_metadata": {"B": b"test-metadata"},
                }
            },
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        # Stub DynamoDB delete_item call
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "Item deleted successfully"
        assert body["item_id"] == item_id

    def test_delete_item_route_enforces_user_authorization(
        self, mock_service_provider, dynamodb_stubber, items_table_name
    ):
        """
        Test that delete item route enforces user ownership authorization.

        Returns 404 if item exists but belongs to a different user.
        This reduces information leakage by not revealing item existence.
        """
        user_id = "test-user-123"
        different_user_id = "different-user-456"
        item_id = "test-item-123"
        vault_id = "test-vault-456"

        # Stub DynamoDB get_item call - returns item owned by different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": different_user_id},  # Different user owns this item
                    "vault_id": {"S": vault_id},
                    "item_type": {"S": "NOTE"},
                    "encrypted_metadata": {"B": b"test-metadata"},
                }
            },
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["statusCode"] == 404

    def test_delete_item_route_returns_404_for_nonexistent_item(
        self, mock_service_provider, dynamodb_stubber, items_table_name
    ):
        """Test delete item route returns 404 when item doesn't exist."""
        user_id = "test-user-123"
        item_id = "nonexistent-item"

        # Stub DynamoDB get_item call - returns empty (no item found)
        dynamodb_stubber.add_response(
            "get_item",
            {},  # Empty response means item not found
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 404


class TestDownloadItemRoute:
    """Test suite for DownloadItemRoute through lambda handler."""

    def test_download_item_route_handler(
        self, mock_service_provider, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test download item route handler with vault_id."""
        user_id = "test-user-123"
        item_id = "test-item-123"
        vault_id = "vault-123"
        s3_key = f"vaults/{vault_id}/files/{item_id}/test"

        event = {
            "resource": "/v1/items/{item_id}/download",
            "path": f"/v1/items/{item_id}/download",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            # TODO does this need to be a queryStringParam and instead in the request payload?
            "queryStringParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": f"VAULT#{vault_id}"},
                    "s3_key": {"S": s3_key},
                    "item_type": {"S": "MEDIA"},
                    "upload_status": {"S": "COMPLETED"},
                    "encrypted_metadata": {"B": "foobar".encode()},
                }
            },
            expected_params={
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"ITEM#{item_id}",
                },
            },
        )

        s3_stubber.add_response(
            "head_object", {}, expected_params={"Bucket": files_bucket_name, "Key": s3_key}
        )

        response = lambda_handler(event, {}, mock_service_provider)
        body = json.loads(response["body"])

        assert response["statusCode"] == 200
        assert body["s3_key"] == s3_key
        assert s3_key in body["download_url"]


class TestSearchItemRoute:
    """Test suite for SearchItemsRoute through lambda handler."""

    def test_search_items_route_handler(self, mock_service_provider):
        """Test search items route handler returns expected response."""
        event = {
            "resource": "/v1/items/search",
            "path": "/v1/items/search",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Search items endpoint" in body["message"]
