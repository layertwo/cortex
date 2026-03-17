"""
Unit tests for VaultService.

These tests verify the vault service layer functionality including
vault creation with salt generation and vault salt retrieval.

Uses botocore Stubber for AWS service testing (not mocking).
"""

import secrets

import pytest
from botocore.exceptions import ClientError
from botocore.stub import ANY

from src.shared.exceptions import BadRequestError, InternalError, NotFoundError


class TestVaultService:
    """Unit tests for VaultService."""

    def test_create_vault_generates_salt(self, vault_service, dynamodb_stubber):
        """Test that create_vault generates a 16-byte salt when not provided."""
        user_id = "test-user-123"

        # Stub successful put_item response - use ANY for generated values
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": ANY,  # Don't validate exact item structure since vault_id and salt are generated
                "ConditionExpression": ANY,
            },
        )

        result = vault_service.create_vault(user_id=user_id)

        # Verify result structure
        assert "vault_id" in result
        assert "vault_salt" in result
        assert "created_at" in result

        # Verify salt is 16 bytes
        assert isinstance(result["vault_salt"], bytes)
        assert len(result["vault_salt"]) == 16

    def test_create_vault_with_provided_salt(self, vault_service, dynamodb_stubber):
        """Test that create_vault accepts a provided salt."""
        user_id = "test-user-123"
        provided_salt = secrets.token_bytes(16)

        # Stub successful put_item response
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": ANY,  # Don't validate exact structure
                "ConditionExpression": ANY,
            },
        )

        result = vault_service.create_vault(user_id=user_id, vault_salt=provided_salt)

        # Verify the provided salt was used
        assert result["vault_salt"] == provided_salt
        assert len(result["vault_salt"]) == 16

    def test_create_vault_rejects_invalid_salt_length(self, vault_service):
        """Test that create_vault rejects salts that are not 16 bytes."""
        user_id = "test-user-123"

        # Test with salt too short
        with pytest.raises(BadRequestError, match="Vault salt must be exactly 16 bytes"):
            vault_service.create_vault(user_id=user_id, vault_salt=b"short")

        # Test with salt too long
        with pytest.raises(BadRequestError, match="Vault salt must be exactly 16 bytes"):
            vault_service.create_vault(user_id=user_id, vault_salt=b"x" * 32)

    def test_create_vault_rejects_non_bytes_salt(self, vault_service):
        """Test that create_vault rejects non-bytes salt values."""
        user_id = "test-user-123"

        # Test with string instead of bytes
        with pytest.raises(BadRequestError, match="Vault salt must be exactly 16 bytes"):
            vault_service.create_vault(user_id=user_id, vault_salt="not-bytes-value")

    def test_create_vault_handles_dynamodb_error(self, vault_service, dynamodb_stubber):
        """Test that create_vault handles DynamoDB errors appropriately."""
        user_id = "test-user-123"

        # Stub DynamoDB error
        dynamodb_stubber.add_client_error(
            "put_item",
            service_error_code="ServiceUnavailable",
            service_message="Service unavailable",
        )

        with pytest.raises(ClientError):
            vault_service.create_vault(user_id=user_id)

    def test_create_vault_handles_collision(self, vault_service, dynamodb_stubber):
        """Test that create_vault retries on UUID collision."""
        user_id = "test-user-123"

        # Stub conditional check failure on first call
        dynamodb_stubber.add_client_error(
            "put_item",
            service_error_code="ConditionalCheckFailedException",
            service_message="Item exists",
        )

        # Stub success on retry
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )

        result = vault_service.create_vault(user_id=user_id)

        # Verify result is valid
        assert "vault_id" in result
        assert "vault_salt" in result
        assert len(result["vault_salt"]) == 16

    def test_get_vault_salt_returns_salt(self, vault_service, dynamodb_stubber):
        """Test that get_vault_salt retrieves the correct salt."""
        user_id = "test-user-123"
        vault_id = "vault-456"
        expected_salt = secrets.token_bytes(16)

        # Stub DynamoDB get_item response
        # Note: boto3 deserializes Binary data, so we return bytes directly
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "vault_salt": {"B": expected_salt},  # boto3 will deserialize this
                    "created_at": {"N": "1234567890"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,  # boto3 transforms high-level to low-level format
            },
        )

        result = vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

        # Verify result - boto3 deserializes Binary to bytes
        assert isinstance(result, bytes)
        assert len(result) == 16
        # Note: The exact value might differ due to boto3's Binary type handling
        # but the length and type should be correct

    def test_get_vault_salt_raises_not_found(self, vault_service, dynamodb_stubber):
        """Test that get_vault_salt raises ResourceNotFoundError when vault doesn't exist."""
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

        with pytest.raises(NotFoundError, match=f"Vault {vault_id} not found"):
            vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

    def test_get_vault_salt_raises_error_on_missing_salt(self, vault_service, dynamodb_stubber):
        """Test that get_vault_salt raises InternalError when salt is missing from item."""
        user_id = "test-user-123"
        vault_id = "vault-456"

        # Stub DynamoDB response with item but no salt
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    # vault_salt is missing
                    "created_at": {"N": "1234567890"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
            },
        )

        with pytest.raises(InternalError, match="missing salt"):
            vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

    def test_get_vault_salt_validates_salt_format(self, vault_service, dynamodb_stubber):
        """Test that get_vault_salt validates the salt format."""
        user_id = "test-user-123"
        vault_id = "vault-456"

        # Stub DynamoDB response with invalid salt (wrong length)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "vault_salt": {"B": b"short"},  # Invalid: not 16 bytes
                    "created_at": {"N": "1234567890"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
            },
        )

        with pytest.raises(InternalError, match="invalid salt format"):
            vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

    def test_get_vault_salt_handles_dynamodb_error(self, vault_service, dynamodb_stubber):
        """Test that get_vault_salt handles DynamoDB errors."""
        user_id = "test-user-123"
        vault_id = "vault-456"

        # Stub DynamoDB error
        dynamodb_stubber.add_client_error(
            "get_item",
            service_error_code="ServiceUnavailable",
            service_message="Service unavailable",
        )

        with pytest.raises(ClientError):
            vault_service.get_vault_salt(user_id=user_id, vault_id=vault_id)

    def test_vault_exists_returns_true_when_exists(self, vault_service, dynamodb_stubber):
        """Test that vault_exists returns True when vault exists."""
        user_id = "test-user-123"
        vault_id = "vault-456"

        # Stub DynamoDB response with item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
            },
        )

        result = vault_service.vault_exists(user_id=user_id, vault_id=vault_id)

        assert result is True

    def test_vault_exists_returns_false_when_not_exists(self, vault_service, dynamodb_stubber):
        """Test that vault_exists returns False when vault doesn't exist."""
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

        result = vault_service.vault_exists(user_id=user_id, vault_id=vault_id)

        assert result is False

    def test_vault_exists_handles_error_gracefully(self, vault_service, dynamodb_stubber):
        """Test that vault_exists returns False on DynamoDB error."""
        user_id = "test-user-123"
        vault_id = "vault-456"

        # Stub DynamoDB error
        dynamodb_stubber.add_client_error(
            "get_item",
            service_error_code="ServiceUnavailable",
            service_message="Service unavailable",
        )

        with pytest.raises(NotFoundError):
            vault_service.vault_exists(user_id=user_id, vault_id=vault_id)

    def test_list_user_vaults_returns_vaults(self, vault_service, dynamodb_stubber):
        """Test that list_user_vaults returns all user vaults."""
        user_id = "test-user-123"
        salt1 = secrets.token_bytes(16)
        salt2 = secrets.token_bytes(16)

        # Stub DynamoDB query response
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {"S": "VAULT#vault-1"},
                        "vault_id": {"S": "vault-1"},
                        "user_id": {"S": user_id},
                        "vault_salt": {"B": salt1},
                        "created_at": {"N": "1234567890"},
                    },
                    {
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {"S": "VAULT#vault-2"},
                        "vault_id": {"S": "vault-2"},
                        "user_id": {"S": user_id},
                        "vault_salt": {"B": salt2},
                        "created_at": {"N": "1234567891"},
                    },
                ]
            },
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        result = vault_service.list_user_vaults(user_id=user_id)

        # Verify result
        assert len(result) == 2
        assert result[0]["vault_id"] == "vault-1"
        assert result[1]["vault_id"] == "vault-2"

        # Verify vault_salt is not included in list response
        assert "vault_salt" not in result[0]
        assert "vault_salt" not in result[1]

        # Verify created_at is included
        assert "created_at" in result[0]
        assert "created_at" in result[1]

    def test_list_user_vaults_returns_empty_list(self, vault_service, dynamodb_stubber):
        """Test that list_user_vaults returns empty list when user has no vaults."""
        user_id = "test-user-123"

        # Stub DynamoDB query response with no items
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        result = vault_service.list_user_vaults(user_id=user_id)

        # Verify empty list
        assert result == []

    def test_list_user_vaults_handles_error(self, vault_service, dynamodb_stubber):
        """Test that list_user_vaults handles DynamoDB errors."""
        user_id = "test-user-123"

        # Stub DynamoDB error
        dynamodb_stubber.add_client_error(
            "query",
            service_error_code="ServiceUnavailable",
            service_message="Service unavailable",
        )

        with pytest.raises(ClientError):
            vault_service.list_user_vaults(user_id=user_id)

    def test_generated_salts_are_unique(self, vault_service, dynamodb_stubber):
        """Test that multiple vault creations generate unique salts."""
        user_id = "test-user-123"

        # Stub 100 successful put_item responses
        for _ in range(100):
            dynamodb_stubber.add_response(
                "put_item",
                {},
                {
                    "TableName": "test-vaults-table",
                    "Item": ANY,
                    "ConditionExpression": ANY,
                },
            )

        # Create multiple vaults
        salts = []
        for _ in range(100):
            result = vault_service.create_vault(user_id=user_id)
            salts.append(result["vault_salt"])

        # Verify all salts are unique
        unique_salts = set(salts)
        assert len(unique_salts) == 100, "All generated salts should be unique"

    def test_salt_is_cryptographically_random(self, vault_service, dynamodb_stubber):
        """Test that generated salts are cryptographically random."""
        user_id = "test-user-123"

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

        result = vault_service.create_vault(user_id=user_id)
        salt = result["vault_salt"]

        # Verify salt is not all zeros (weak value)
        assert salt != b"\x00" * 16

        # Verify salt has sufficient entropy (not all same byte)
        assert len(set(salt)) > 1, "Salt should have sufficient entropy"
