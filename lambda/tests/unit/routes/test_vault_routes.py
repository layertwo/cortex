"""
Unit tests for vault route handlers.

Tests verify that vault routes work correctly through the FastAPI test client.
Uses botocore Stubber for AWS service testing (not mocking).
"""

import base64
import secrets

import pytest
from botocore.stub import ANY


class TestCreateVaultRoute:
    """Test suite for CreateVaultRoute through FastAPI test client."""

    def test_create_vault_route_handler_generates_salt(self, client, dynamodb_stubber):
        """Test create vault route handler generates salt and returns vault ID."""
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

        response = client.post("/v1/vaults", json={})

        assert response.status_code == 200
        body = response.json()
        # camelCase wire (Smithy contract); response now includes the salt.
        assert "vaultId" in body
        assert "vaultSalt" in body
        assert "createdAt" in body

    def test_create_vault_route_handler_accepts_encrypted_name(self, client, dynamodb_stubber):
        """Test create vault route handler accepts the optional encrypted name."""
        encrypted_name = secrets.token_bytes(32)

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

        response = client.post(
            "/v1/vaults",
            json={"encryptedName": base64.b64encode(encrypted_name).decode("utf-8")},
        )

        assert response.status_code == 200
        body = response.json()
        assert "vaultId" in body


class TestGetVaultSaltRoute:
    """Test suite for GetVaultSaltRoute through FastAPI test client."""

    def test_get_vault_salt_route_handler_returns_salt(self, client, dynamodb_stubber):
        """Test get vault salt route handler returns vault salt."""
        user_id = "test-user-id"
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

        response = client.get(f"/v1/vaults/{vault_id}/salt")

        assert response.status_code == 200
        body = response.json()
        # GetVaultSaltOutput is vaultSalt only (no vaultId in the contract).
        assert "vaultSalt" in body

    def test_get_vault_salt_route_handler_vault_not_found(self, client, dynamodb_stubber):
        """Test get vault salt route handler returns 404 when vault not found."""
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

        response = client.get(f"/v1/vaults/{vault_id}/salt")

        assert response.status_code == 404
        body = response.json()
        assert "not found" in body["error"]["message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
