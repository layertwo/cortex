"""
Unit tests for vault route handlers.

Tests verify that vault routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestCreateVaultRoute:
    """Test suite for CreateVaultRoute through lambda handler."""

    def test_create_vault_route_handler(self, mock_service_provider):
        """Test create vault route handler returns expected response."""
        event = {
            "resource": "/v1/vaults",
            "path": "/v1/vaults",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Create vault endpoint" in body["message"]


class TestGetVaultSaltRoute:
    """Test suite for GetVaultSaltRoute through lambda handler."""

    def test_get_vault_salt_route_handler(self, mock_service_provider):
        """Test get vault salt route handler returns expected response."""
        vault_id = "test-vault-123"
        event = {
            "resource": "/v1/vaults/{vault_id}/salt",
            "path": f"/v1/vaults/{vault_id}/salt",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"vault_id": vault_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Get vault salt endpoint" in body["message"]
