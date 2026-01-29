"""
Unit tests for collection route handlers.

Tests verify that collection routes work correctly through the lambda handler entrypoint.
"""

import json
from datetime import datetime

from botocore.stub import ANY

from src.entrypoint.api import lambda_handler


class TestCreateCollectionRoute:
    """Test suite for CreateCollectionRoute through lambda handler."""

    def test_create_collection_route_handler(
        self, mock_service_provider, dynamodb_stubber, vaults_table_name
    ):
        """Test create collection route handler returns expected response."""
        user_id = "test-user-123"
        vault_id = "test-vault-456"

        # Stub vault ownership check (get_item for vault)
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
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        # Stub DynamoDB put_item call (create collection)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": ANY,
                "Item": ANY,
            },
        )

        event = {
            "resource": "/v1/collections",
            "path": "/v1/collections",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_id": vault_id,
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",  # base64 encoded
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "collection_id" in body, "Response should include collection_id"
        assert "created_at" in body, "Response should include created_at"

        # Verify response values
        assert isinstance(body["collection_id"], str), "collection_id should be a string"
        assert len(body["collection_id"]) > 0, "collection_id should not be empty"

        # Validate created_at is ISO format datetime string
        try:
            datetime.fromisoformat(body["created_at"])
        except ValueError:
            raise AssertionError(
                f"created_at should be ISO format datetime, got {body['created_at']}"
            )

    def test_create_collection_route_handler_missing_vault_id(self, mock_service_provider):
        """Test create collection route handler returns error when vault_id is missing."""
        event = {
            "resource": "/v1/collections",
            "path": "/v1/collections",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body


class TestListCollectionsRoute:
    """Test suite for ListCollectionsRoute through lambda handler."""

    def test_list_collections_route_handler_missing_vault_id(self, mock_service_provider):
        """Test list collections route handler returns error when vault_id is missing."""
        event = {
            "resource": "/v1/collections",
            "path": "/v1/collections",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "vault_id is required"}
        assert body["statusCode"] == 400
        assert "vault_id is required" in body["message"]


class TestGetCollectionRoute:
    """Test suite for GetCollectionRoute through lambda handler."""

    def test_get_collection_route_handler_missing_vault_id(self, mock_service_provider):
        """Test get collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}",
            "path": f"/v1/collections/{collection_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "queryStringParameters": {},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "vault_id is required"}
        assert body["statusCode"] == 400
        assert "vault_id is required" in body["message"]


class TestUpdateCollectionRoute:
    """Test suite for UpdateCollectionRoute through lambda handler."""

    def test_update_collection_route_handler_missing_vault_id(self, mock_service_provider):
        """Test update collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}",
            "path": f"/v1/collections/{collection_id}",
            "httpMethod": "PUT",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "body": json.dumps(
                {
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body


class TestDeleteCollectionRoute:
    """Test suite for DeleteCollectionRoute through lambda handler."""

    def test_delete_collection_route_handler_missing_vault_id(self, mock_service_provider):
        """Test delete collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}",
            "path": f"/v1/collections/{collection_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "queryStringParameters": {},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "vault_id is required"}
        assert body["statusCode"] == 400
        assert "vault_id is required" in body["message"]


class TestAddItemToCollectionRoute:
    """Test suite for AddItemToCollectionRoute through lambda handler."""

    def test_add_item_to_collection_route_handler_missing_vault_id(self, mock_service_provider):
        """Test add item to collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}/items",
            "path": f"/v1/collections/{collection_id}/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "body": json.dumps(
                {
                    "item_id": "item-456",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body

    def test_add_item_to_collection_route_handler_missing_item_id(self, mock_service_provider):
        """Test add item to collection route handler returns error when item_id is missing."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}/items",
            "path": f"/v1/collections/{collection_id}/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "body": json.dumps(
                {
                    "vault_id": "vault-123",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body


class TestRemoveItemFromCollectionRoute:
    """Test suite for RemoveItemFromCollectionRoute through lambda handler."""

    def test_remove_item_from_collection_route_handler_missing_vault_id(
        self, mock_service_provider
    ):
        """Test remove item from collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"
        item_id = "test-item-456"
        event = {
            "resource": "/v1/collections/{collection_id}/items/{item_id}",
            "path": f"/v1/collections/{collection_id}/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id, "item_id": item_id},
            "queryStringParameters": {},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "vault_id is required"}
        assert body["statusCode"] == 400
        assert "vault_id is required" in body["message"]
