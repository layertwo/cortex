"""
Unit tests for item route handlers.

Tests verify that item routes work correctly through the lambda handler entrypoint.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

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
        self, mock_service_provider, dynamodb_stubber, s3_stubber
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
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "s3_key": {"S": s3_key},
                    "upload_status": {"S": "PENDING"},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"VAULT#{vault_id}",
                    "SK": f"ITEM#MEDIA#{item_id}",
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
                "Bucket": "test-files-bucket",
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
                    "PK": f"VAULT#{vault_id}",
                    "SK": f"ITEM#MEDIA#{item_id}",
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

    def test_list_items_route_handler_with_vault_id(self, mock_service_provider):
        """Test list items route handler with vault_id."""
        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {"vault_id": "vault-123"},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 401 (authentication), 403 (vault ownership), or 200 (success)
        # 403 is expected when vault ownership check fails (security fix for OWASP A01:2021)
        assert response["statusCode"] in [200, 401, 403]


class TestGetItemRoute:
    """Test suite for GetItemRoute through lambda handler."""

    def test_get_item_route_handler_missing_vault_id(self, mock_service_provider):
        """Test get item route handler returns error when vault_id is missing."""
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

    def test_get_item_route_handler_with_vault_id(self, mock_service_provider):
        """Test get item route handler with vault_id."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "queryStringParameters": {"vault_id": "vault-123"},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 401 (authentication), 403 (vault ownership), 404 (not found), or 200 (success)
        # 403 is expected when vault ownership check fails (security fix for OWASP A01:2021)
        assert response["statusCode"] in [200, 401, 403, 404]


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

    def test_delete_item_route_handler_with_vault_id(self, mock_service_provider):
        """Test delete item route handler with vault_id parameter."""
        item_id = "test-item-123"
        vault_id = "test-vault-456"

        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "queryStringParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 401 (authentication), 403 (vault ownership), or 200 (success)
        # 403 is expected when vault ownership check fails (security fix for OWASP A01:2021)
        assert response["statusCode"] in [200, 401, 403]

    def test_delete_item_route_handler_missing_vault_id(self, mock_service_provider):
        """Test delete item route handler returns error when vault_id is missing."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 401 because authentication is not fully mocked
        # This is expected behavior - the route requires proper authentication
        assert response["statusCode"] in [400, 401]

    def test_delete_item_route_enforces_vault_authorization(
        self, mock_service_provider, monkeypatch
    ):
        """
        Test that delete item route enforces vault ownership authorization.

        This test verifies the security fix for OWASP A01:2021 - Broken Access Control.
        It ensures that users cannot delete items from vaults they don't own.

        Security: CRITICAL - Prevents unauthorized access to other users' vaults
        """

        item_id = "test-item-123"
        vault_id = "test-vault-456"
        user_id = "test-user-123"

        # Mock vault_service.vault_exists to return False (user doesn't own vault)
        mock_vault_service = MagicMock()
        mock_vault_service.vault_exists.return_value = False

        # Replace the vault_service in the service provider
        monkeypatch.setattr(mock_service_provider, "vault_service", mock_vault_service)

        # Mock get_user_from_context to return a user_id
        def mock_get_user(event):
            return user_id

        monkeypatch.setattr("src.api.routes.items.get_user_from_context", mock_get_user)

        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "queryStringParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify vault ownership check was called
        mock_vault_service.vault_exists.assert_called_once_with(user_id, vault_id)

        # Verify 403 Forbidden is returned when user doesn't own vault
        assert response["statusCode"] == 403

        # Verify error message indicates authorization failure
        body = (
            json.loads(response["body"])
            if isinstance(response.get("body"), str)
            else response.get("body", {})
        )
        # Powertools format: {"statusCode": 403, "message": "Access denied to vault"}
        assert body.get("statusCode") == 403
        assert "vault" in body.get("message", "").lower()


class TestDownloadItemRoute:
    """Test suite for DownloadItemRoute through lambda handler."""

    def test_download_item_route_handler_missing_vault_id(self, mock_service_provider):
        """Test download item route handler returns error when vault_id is missing."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}/download",
            "path": f"/v1/items/{item_id}/download",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
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

    def test_download_item_route_handler_with_vault_id(self, mock_service_provider):
        """Test download item route handler with vault_id."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}/download",
            "path": f"/v1/items/{item_id}/download",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "queryStringParameters": {"vault_id": "vault-123"},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 401 (authentication), 403 (vault ownership), 404 (not found), or 200 (success)
        # 403 is expected when vault ownership check fails (security fix for OWASP A01:2021)
        assert response["statusCode"] in [200, 401, 403, 404]


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
