"""
Unit tests for vault route handlers.

Tests verify that vault routes work correctly through the FastAPI test client.
Uses botocore Stubber for AWS service testing (not mocking).
"""

import base64
import secrets

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


class TestGetVaultRoute:
    def test_get_vault_returns_vault_with_rotation_state(self, client, dynamodb_stubber):
        # Matches the fixed user_id the `client` fixture overrides
        # get_current_user to return (see tests/conftest.py).
        user_id = "test-user-id"
        vault_id = "test-vault-1"
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "vault_salt": {"B": b"\xaa" * 16},
                    "created_at": {"N": "1700000000"},
                    "updated_at": {"N": "1700000000"},
                    "kek_version": {"N": "1"},
                    "rotation_state": {"S": "IDLE"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )
        response = client.get(f"/v1/vaults/{vault_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["vaultId"] == vault_id
        assert body["rotationState"] == "IDLE"
        assert body["kekVersion"] == 1


class TestUpdateVaultRotationRoute:
    def test_acquire_rotation_lock(self, client, dynamodb_stubber):
        import time

        vault_id = "test-vault-1"
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": str(int(time.time()))},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "ACQUIRE", "expectedState": "IDLE"},
        )
        assert response.status_code == 200
        assert response.json()["rotationState"] == "IN_PROGRESS"

    def test_conflict_returns_409(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "ACQUIRE", "expectedState": "IDLE"},
        )
        assert response.status_code == 409
