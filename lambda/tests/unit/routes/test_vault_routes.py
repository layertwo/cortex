"""
Unit tests for vault route handlers.

Tests verify that vault routes work correctly through the lambda handler entrypoint.
Uses botocore Stubber for AWS service testing (not mocking).
"""

import base64
import json
import secrets

import pytest
from botocore.stub import ANY

from src.entrypoint.api import lambda_handler


class TestCreateVaultRoute:
    """Test suite for CreateVaultRoute through lambda handler."""

    def test_create_vault_route_handler_generates_salt(
        self, mock_service_provider, dynamodb_stubber
    ):
        """Test create vault route handler generates salt and returns vault ID."""
        user_id = "test-user-123"

        # Stub successful put_item response - use ANY for dynamic values
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )

        # Create event with authenticated user
        event = {
            "resource": "/v1/vaults",
            "path": "/v1/vaults",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "vault_id" in body
        assert "created_at" in body

    def test_create_vault_route_handler_with_provided_salt(
        self, mock_service_provider, dynamodb_stubber
    ):
        """Test create vault route handler accepts provided salt."""
        user_id = "test-user-123"
        provided_salt = secrets.token_bytes(16)

        # Stub successful put_item response
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )

        # Create event with provided salt (base64-encoded in JSON)
        event = {
            "resource": "/v1/vaults",
            "path": "/v1/vaults",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"vault_salt": base64.b64encode(provided_salt).decode("utf-8")}),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "vault_id" in body


class TestGetVaultSaltRoute:
    """Test suite for GetVaultSaltRoute through lambda handler."""

    def test_get_vault_salt_route_handler_returns_salt(
        self, mock_service_provider, dynamodb_stubber
    ):
        """Test get vault salt route handler returns vault salt."""
        user_id = "test-user-123"
        vault_id = "test-vault-123"
        vault_salt = secrets.token_bytes(16)

        # Stub DynamoDB get_item response
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "vault_salt": {"B": vault_salt},
                    "created_at": {"N": "1234567890"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
            },
        )

        # Create event with authenticated user
        event = {
            "resource": "/v1/vaults/{vault_id}/salt",
            "path": f"/v1/vaults/{vault_id}/salt",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["vault_id"] == vault_id
        # vault_salt should be base64-encoded in response
        assert "vault_salt" in body

    def test_get_vault_salt_route_handler_vault_not_found(
        self, mock_service_provider, dynamodb_stubber
    ):
        """Test get vault salt route handler returns 404 when vault not found."""
        user_id = "test-user-123"
        vault_id = "nonexistent-vault"

        # Stub DynamoDB response with no item
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
            },
        )

        # Create event with authenticated user
        event = {
            "resource": "/v1/vaults/{vault_id}/salt",
            "path": f"/v1/vaults/{vault_id}/salt",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"vault_id": vault_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify 404 response
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 404, "message": "Vault ... not found"}
        assert body["statusCode"] == 404
        assert "not found" in body["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
