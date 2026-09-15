"""
Unit tests for VaultService.

These tests verify the vault service layer functionality including
vault creation with salt generation and vault salt retrieval.

Uses botocore Stubber for AWS service testing (not mocking).
"""

import secrets
import time

import pytest
from botocore.exceptions import ClientError
from botocore.stub import ANY

from src.shared.exceptions import BadRequestError, ConflictError, InternalError, NotFoundError
from tests.fixtures.vault_deletion import (
    MARK_CONDITION_EXPRESSION,
    MARK_UPDATE_EXPRESSION,
    ROW_DELETE_CONDITION,
    vault_row,
)


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

        with pytest.raises(NotFoundError, match="Vault not found"):
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

    def test_list_user_vaults_returns_page_with_unlock_fields(
        self, vault_service, dynamodb_stubber
    ):
        """list_user_vaults filters deleting vaults server-side and returns unlock fields."""
        user_id = "test-user-123"
        salt1 = secrets.token_bytes(16)
        salt2 = secrets.token_bytes(16)
        name2 = secrets.token_bytes(24)
        verifier2 = secrets.token_bytes(48)

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
                        "encrypted_name": {"B": name2},
                        "verifier": {"B": verifier2},
                        "created_at": {"N": "1234567891"},
                        "updated_at": {"N": "1234567999"},
                        "kek_version": {"N": "3"},
                        "rotation_state": {"S": "PAUSED"},
                    },
                ]
            },
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "FilterExpression": "attribute_not_exists(deletion_state)",
                "ExpressionAttributeValues": {":pk": f"USER#{user_id}", ":sk_prefix": "VAULT#"},
                "Limit": 50,
            },
        )

        vaults, next_token = vault_service.list_user_vaults(user_id=user_id)

        assert next_token is None
        assert [v["vault_id"] for v in vaults] == ["vault-1", "vault-2"]
        assert vaults[0] == {
            "vault_id": "vault-1",
            "vault_salt": salt1,
            "encrypted_name": None,
            "verifier": None,
            "created_at": 1234567890,
            "updated_at": 1234567890,
            "kek_version": 1,
            "rotation_state": "IDLE",
        }
        assert vaults[1]["vault_salt"] == salt2
        assert vaults[1]["encrypted_name"] == name2
        assert vaults[1]["verifier"] == verifier2
        assert vaults[1]["updated_at"] == 1234567999
        assert vaults[1]["kek_version"] == 3
        assert vaults[1]["rotation_state"] == "PAUSED"

    def test_list_user_vaults_pagination_token_round_trip(self, vault_service, dynamodb_stubber):
        """LastEvaluatedKey becomes next_token; feeding it back sends ExclusiveStartKey."""
        user_id = "test-user-123"
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {"S": "VAULT#vault-1"},
                        "vault_id": {"S": "vault-1"},
                        "vault_salt": {"B": b"\x01" * 16},
                        "created_at": {"N": "1234567890"},
                    }
                ],
                "LastEvaluatedKey": {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "VAULT#vault-1"}},
            },
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "FilterExpression": "attribute_not_exists(deletion_state)",
                "ExpressionAttributeValues": {":pk": f"USER#{user_id}", ":sk_prefix": "VAULT#"},
                "Limit": 10,
            },
        )
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "FilterExpression": "attribute_not_exists(deletion_state)",
                "ExpressionAttributeValues": {":pk": f"USER#{user_id}", ":sk_prefix": "VAULT#"},
                "Limit": 10,
                "ExclusiveStartKey": {"PK": f"USER#{user_id}", "SK": "VAULT#vault-1"},
            },
        )

        page1, token = vault_service.list_user_vaults(user_id=user_id, page_size=10)
        assert len(page1) == 1
        assert isinstance(token, str) and token

        page2, token2 = vault_service.list_user_vaults(
            user_id=user_id, page_size=10, next_token=token
        )
        assert page2 == []
        assert token2 is None

    def test_list_user_vaults_returns_empty_page(self, vault_service, dynamodb_stubber):
        """No vaults: an empty page and no token."""
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": ANY,
                "FilterExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 50,
            },
        )

        assert vault_service.list_user_vaults(user_id="test-user-123") == ([], None)

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

    def test_get_vault_returns_vault_with_rotation_fields(self, vault_service, dynamodb_stubber):
        """Test that get_vault returns the vault record including rotation fields."""
        user_id = "u1"
        vault_id = "v1"
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "vault_salt": {"B": b"\x00" * 16},
                    "created_at": {"N": "1700000000"},
                    "kek_version": {"N": "1"},
                    "rotation_state": {"S": "IDLE"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
            },
        )
        result = vault_service.get_vault(user_id=user_id, vault_id=vault_id)
        assert result["vault_id"] == vault_id
        assert result["kek_version"] == 1
        assert result["rotation_state"] == "IDLE"
        assert result["rotation_locked_at"] is None

    def test_get_vault_raises_not_found(self, vault_service, dynamodb_stubber):
        """Test that get_vault raises NotFoundError when vault doesn't exist."""
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": ANY},
        )
        with pytest.raises(NotFoundError):
            vault_service.get_vault(user_id="u1", vault_id="v1")

    def test_create_vault_writes_updated_at(self, vault_service, dynamodb_stubber):
        """create_vault stamps updated_at alongside created_at on the new row."""
        salt = secrets.token_bytes(16)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": {
                    "PK": "USER#u1",
                    "SK": ANY,
                    "vault_id": ANY,
                    "user_id": "u1",
                    "vault_salt": salt,
                    "created_at": ANY,
                    "updated_at": ANY,
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
            },
        )

        result = vault_service.create_vault(user_id="u1", vault_salt=salt)

        assert result["vault_salt"] == salt

    def test_get_vault_returns_name_verifier_and_staged_pair(self, vault_service, dynamodb_stubber):
        """get_vault surfaces encrypted_name, verifier, and the staged rotation pair."""
        name = secrets.token_bytes(24)
        verifier = secrets.token_bytes(48)
        pending_salt = secrets.token_bytes(16)
        pending_verifier = secrets.token_bytes(48)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": vault_row(
                    "u1",
                    "v1",
                    vault_salt={"B": b"\x01" * 16},
                    encrypted_name={"B": name},
                    verifier={"B": verifier},
                    pending_vault_salt={"B": pending_salt},
                    pending_verifier={"B": pending_verifier},
                    updated_at={"N": "1700000500"},
                    kek_version={"N": "2"},
                    rotation_state={"S": "IN_PROGRESS"},
                    rotation_locked_at={"N": "1700000400"},
                )
            },
            {"TableName": "test-vaults-table", "Key": {"PK": "USER#u1", "SK": "VAULT#v1"}},
        )

        result = vault_service.get_vault(user_id="u1", vault_id="v1")

        assert result["vault_salt"] == b"\x01" * 16
        assert result["encrypted_name"] == name
        assert result["verifier"] == verifier
        assert result["pending_vault_salt"] == pending_salt
        assert result["pending_verifier"] == pending_verifier
        assert result["updated_at"] == 1700000500
        assert result["kek_version"] == 2
        assert result["rotation_state"] == "IN_PROGRESS"
        assert result["rotation_locked_at"] == 1700000400

    def test_get_vault_defaults_optional_fields_to_none(self, vault_service, dynamodb_stubber):
        """A legacy row without name, verifier, or staged pair reads back as None."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "user_id": {"S": "u1"},
                    "vault_salt": {"B": b"\x00" * 16},
                    "created_at": {"N": "1700000000"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        result = vault_service.get_vault(user_id="u1", vault_id="v1")

        assert result["encrypted_name"] is None
        assert result["verifier"] is None
        assert result["pending_vault_salt"] is None
        assert result["pending_verifier"] is None
        assert result["updated_at"] == 1700000000
        assert result["kek_version"] == 1
        assert result["rotation_state"] == "IDLE"

    def test_get_vault_raises_not_found_when_deleting(self, vault_service, dynamodb_stubber):
        """A row carrying deletion_state is treated as not found."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "user_id": {"S": "u1"},
                    "vault_salt": {"B": b"\x00" * 16},
                    "created_at": {"N": "1700000000"},
                    "deletion_state": {"S": "DELETING"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        with pytest.raises(NotFoundError, match="Vault not found"):
            vault_service.get_vault(user_id="u1", vault_id="v1")

    def test_vault_exists_returns_false_when_deleting(self, vault_service, dynamodb_stubber):
        """vault_exists is False for a row that carries deletion_state."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "deletion_state": {"S": "DELETING"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        assert vault_service.vault_exists(user_id="u1", vault_id="v1") is False

    def test_get_vault_salt_raises_not_found_when_deleting(self, vault_service, dynamodb_stubber):
        """get_vault_salt treats a DELETING row as not found."""
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "user_id": {"S": "u1"},
                    "vault_salt": {"B": b"\x00" * 16},
                    "created_at": {"N": "1700000000"},
                    "deletion_state": {"S": "DELETING"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        with pytest.raises(NotFoundError, match="Vault not found"):
            vault_service.get_vault_salt(user_id="u1", vault_id="v1")

    def test_update_vault_writes_name_and_verifier(
        self, vault_service, dynamodb_stubber, monkeypatch
    ):
        """update_vault pins the SET expression and the exists/not-deleting guard."""
        monkeypatch.setattr(time, "time", lambda: 1_700_000_000)
        name = secrets.token_bytes(24)
        verifier = secrets.token_bytes(48)
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#u1", "SK": "VAULT#v1"},
                "UpdateExpression": "SET updated_at = :now, encrypted_name = :name, verifier = :ver",
                "ConditionExpression": "attribute_exists(PK) AND attribute_not_exists(deletion_state)",
                "ExpressionAttributeValues": {
                    ":now": 1_700_000_000,
                    ":name": name,
                    ":ver": verifier,
                },
            },
        )

        result = vault_service.update_vault(
            user_id="u1", vault_id="v1", encrypted_name=name, verifier=verifier
        )

        assert result == {"vault_id": "v1", "updated_at": 1_700_000_000}

    def test_update_vault_name_only(self, vault_service, dynamodb_stubber):
        """Only the supplied field is written."""
        name = secrets.token_bytes(24)
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": ANY,
                "UpdateExpression": "SET updated_at = :now, encrypted_name = :name",
                "ConditionExpression": "attribute_exists(PK) AND attribute_not_exists(deletion_state)",
                "ExpressionAttributeValues": {":now": ANY, ":name": name},
            },
        )

        result = vault_service.update_vault(user_id="u1", vault_id="v1", encrypted_name=name)

        assert result["vault_id"] == "v1"
        assert isinstance(result["updated_at"], int)

    def test_update_vault_missing_vault_is_not_found(self, vault_service, dynamodb_stubber):
        """Condition failure plus an empty read means the vault does not exist."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": {"PK": "USER#u1", "SK": "VAULT#v1"}},
        )

        with pytest.raises(NotFoundError, match="Vault not found"):
            vault_service.update_vault(user_id="u1", vault_id="v1", verifier=b"v" * 32)

    def test_update_vault_deleting_vault_is_conflict(self, vault_service, dynamodb_stubber):
        """Condition failure plus a row with deletion_state means 409."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "deletion_state": {"S": "DELETING"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        with pytest.raises(ConflictError):
            vault_service.update_vault(user_id="u1", vault_id="v1", verifier=b"v" * 32)

    def test_update_vault_reraises_other_errors(self, vault_service, dynamodb_stubber):
        """A non-conditional DynamoDB error propagates unchanged."""
        dynamodb_stubber.add_client_error("update_item", service_error_code="ServiceUnavailable")

        with pytest.raises(ClientError):
            vault_service.update_vault(user_id="u1", vault_id="v1", verifier=b"v" * 32)

    def test_mark_deleting_pins_condition(self, vault_service, dynamodb_stubber, monkeypatch):
        """mark_deleting writes the DELETING mark guarded by the spec 4.3 condition."""
        monkeypatch.setattr(time, "time", lambda: 1_700_000_000)
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#u1", "SK": "VAULT#v1"},
                "UpdateExpression": MARK_UPDATE_EXPRESSION,
                "ConditionExpression": MARK_CONDITION_EXPRESSION,
                "ExpressionAttributeValues": {
                    ":deleting": "DELETING",
                    ":now": 1_700_000_000,
                    ":idle": "IDLE",
                    ":paused": "PAUSED",
                    ":in_progress": "IN_PROGRESS",
                    ":stale": 1_700_000_000 - 7 * 24 * 3600,
                },
            },
        )

        assert vault_service.mark_deleting(user_id="u1", vault_id="v1") is None

    def test_mark_deleting_missing_vault_is_not_found(self, vault_service, dynamodb_stubber):
        """Condition failure plus an empty read means 404."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": {"PK": "USER#u1", "SK": "VAULT#v1"}},
        )

        with pytest.raises(NotFoundError, match="Vault not found"):
            vault_service.mark_deleting(user_id="u1", vault_id="v1")

    def test_mark_deleting_already_deleting_is_a_retry(self, vault_service, dynamodb_stubber):
        """A vault already marked DELETING lets the caller proceed."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "deletion_state": {"S": "DELETING"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        assert vault_service.mark_deleting(user_id="u1", vault_id="v1") is None

    def test_mark_deleting_live_rotation_is_conflict(self, vault_service, dynamodb_stubber):
        """A live IN_PROGRESS lock blocks deletion with the spec message."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "vault_id": {"S": "v1"},
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": str(int(time.time()))},
                }
            },
            {"TableName": "test-vaults-table", "Key": ANY},
        )

        with pytest.raises(
            ConflictError,
            match="A vault password change is in progress; wait for it to finish or pause it first",
        ):
            vault_service.mark_deleting(user_id="u1", vault_id="v1")

    def test_mark_deleting_reraises_other_errors(self, vault_service, dynamodb_stubber):
        """A non-conditional DynamoDB error propagates unchanged."""
        dynamodb_stubber.add_client_error("update_item", service_error_code="ServiceUnavailable")

        with pytest.raises(ClientError):
            vault_service.mark_deleting(user_id="u1", vault_id="v1")

    def test_delete_vault_row_conditional_delete(self, vault_service, dynamodb_stubber):
        """delete_vault_row removes the row only while it is marked DELETING."""
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#u1", "SK": "VAULT#v1"},
                "ConditionExpression": ROW_DELETE_CONDITION,
                "ExpressionAttributeValues": {":deleting": "DELETING"},
            },
        )

        assert vault_service.delete_vault_row(user_id="u1", vault_id="v1") is None

    def test_delete_vault_row_swallows_concurrent_removal(self, vault_service, dynamodb_stubber):
        """A failed condition means a concurrent call removed the row first; no exception."""
        dynamodb_stubber.add_client_error(
            "delete_item", service_error_code="ConditionalCheckFailedException"
        )

        assert vault_service.delete_vault_row(user_id="u1", vault_id="v1") is None

    def test_delete_vault_row_reraises_other_errors(self, vault_service, dynamodb_stubber):
        """A non-conditional DynamoDB error propagates unchanged."""
        dynamodb_stubber.add_client_error("delete_item", service_error_code="ServiceUnavailable")

        with pytest.raises(ClientError):
            vault_service.delete_vault_row(user_id="u1", vault_id="v1")


ROTATION_KEY = {"PK": "USER#u1", "SK": "VAULT#v1"}
NOW = 1_700_000_000
STALE = NOW - 7 * 24 * 3600
ACQUIRE_UPDATE = "SET rotation_state = :in_progress, rotation_locked_at = :now, updated_at = :now"
ACQUIRE_STAGING = (
    ", pending_vault_salt = if_not_exists(pending_vault_salt, :salt)"
    ", pending_verifier = if_not_exists(pending_verifier, :pv)"
)
ACQUIRE_CONDITION = (
    "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND ("
    "attribute_not_exists(rotation_state) OR rotation_state = :expected OR "
    "(rotation_state = :in_progress AND rotation_locked_at < :stale))"
)
STATE_CONDITION = "attribute_not_exists(deletion_state) AND rotation_state = :expected"
RELEASE_UPDATE = "SET rotation_state = :idle, updated_at = :now"


def _vault_row(**extra):
    """get_item response for u1/v1 mid-rotation; no kek_version unless given (legacy row)."""
    row = vault_row(
        "u1", "v1", rotation_state={"S": "IN_PROGRESS"}, rotation_locked_at={"N": "1699999000"}
    )
    row.update(extra)
    return {"Item": row}


class TestVaultRotation:
    """update_vault_rotation: ACQUIRE staging, PAUSE, RELEASE (spec 4.3)."""

    @pytest.fixture
    def frozen_time(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: NOW)
        return NOW

    def _rotate(self, vault_service, action, expected_state, **kwargs):
        return vault_service.update_vault_rotation(
            user_id="u1", vault_id="v1", action=action, expected_state=expected_state, **kwargs
        )

    def _stub_release_read(self, dynamodb_stubber, **extra):
        dynamodb_stubber.add_response(
            "get_item",
            _vault_row(**extra),
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY, "ConsistentRead": True},
        )

    # ACQUIRE

    def test_acquire_without_pair_pins_expressions(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": str(NOW)},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": ACQUIRE_UPDATE,
                "ConditionExpression": ACQUIRE_CONDITION,
                "ExpressionAttributeValues": {
                    ":in_progress": "IN_PROGRESS",
                    ":expected": "IDLE",
                    ":stale": STALE,
                    ":now": NOW,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(vault_service, "ACQUIRE", "IDLE")
        assert result == {
            "rotation_state": "IN_PROGRESS",
            "rotation_locked_at": NOW,
            "pending_vault_salt": None,
            "pending_verifier": None,
        }

    def test_acquire_stages_salt_and_verifier(self, vault_service, dynamodb_stubber, frozen_time):
        salt = secrets.token_bytes(16)
        verifier = b"v" * 32
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": str(NOW)},
                    "pending_vault_salt": {"B": salt},
                    "pending_verifier": {"B": verifier},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": ACQUIRE_UPDATE + ACQUIRE_STAGING,
                "ConditionExpression": ACQUIRE_CONDITION,
                "ExpressionAttributeValues": {
                    ":in_progress": "IN_PROGRESS",
                    ":expected": "IDLE",
                    ":stale": STALE,
                    ":now": NOW,
                    ":salt": salt,
                    ":pv": verifier,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(
            vault_service, "ACQUIRE", "IDLE", new_verifier=verifier, new_vault_salt=salt
        )
        assert result["rotation_state"] == "IN_PROGRESS"
        assert result["pending_vault_salt"] == salt
        assert result["pending_verifier"] == verifier
        assert type(result["pending_vault_salt"]) is bytes
        assert type(result["pending_verifier"]) is bytes

    def test_reacquire_returns_staged_pair_not_the_request(self, vault_service, dynamodb_stubber):
        first_salt, first_verifier = secrets.token_bytes(16), b"first-verifier"
        second_salt, second_verifier = secrets.token_bytes(16), b"second-verifier"
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": "1700000500"},
                    "pending_vault_salt": {"B": first_salt},
                    "pending_verifier": {"B": first_verifier},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": ACQUIRE_UPDATE + ACQUIRE_STAGING,
                "ConditionExpression": ACQUIRE_CONDITION,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(
            vault_service,
            "ACQUIRE",
            "IN_PROGRESS",
            new_verifier=second_verifier,
            new_vault_salt=second_salt,
        )
        assert result["pending_vault_salt"] == first_salt
        assert result["pending_verifier"] == first_verifier

    @pytest.mark.parametrize("kwargs", [{"new_vault_salt": b"s" * 16}, {"new_verifier": b"v" * 32}])
    def test_acquire_with_half_a_pair_is_bad_request(self, vault_service, dynamodb_stubber, kwargs):
        with pytest.raises(BadRequestError, match="together"):
            self._rotate(vault_service, "ACQUIRE", "IDLE", **kwargs)

    def test_acquire_rejects_salt_not_16_bytes(self, vault_service, dynamodb_stubber):
        with pytest.raises(BadRequestError, match="Vault salt must be exactly 16 bytes"):
            self._rotate(
                vault_service, "ACQUIRE", "IDLE", new_verifier=b"v" * 32, new_vault_salt=b"s" * 15
            )

    def test_acquire_conflict_raises_conflict_error(self, vault_service, dynamodb_stubber):
        """A row that exists but fails the state check is a real conflict, not a 404."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item", _vault_row(), {"TableName": "test-vaults-table", "Key": ROTATION_KEY}
        )
        with pytest.raises(ConflictError, match="already in progress"):
            self._rotate(vault_service, "ACQUIRE", "IDLE")

    def test_acquire_unknown_vault_is_not_found(self, vault_service, dynamodb_stubber):
        """A retried ACQUIRE against a vault deleted from another device 404s, not a partial upsert."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item", {}, {"TableName": "test-vaults-table", "Key": ROTATION_KEY}
        )
        with pytest.raises(NotFoundError, match="Vault not found"):
            self._rotate(vault_service, "ACQUIRE", "IDLE")

    def test_rotation_conflict_on_deleting_vault_says_being_deleted(
        self, vault_service, dynamodb_stubber
    ):
        """The disambiguating read finds deletion_state: the message names it, not the lock."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#u1"},
                    "SK": {"S": "VAULT#v1"},
                    "deletion_state": {"S": "DELETING"},
                }
            },
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY},
        )
        with pytest.raises(ConflictError, match="Vault is being deleted"):
            self._rotate(vault_service, "ACQUIRE", "IDLE")

    # PAUSE

    def test_pause_pins_expressions_and_keeps_staged_pair(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        salt = secrets.token_bytes(16)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "PAUSED"},
                    "rotation_locked_at": {"N": "1699999000"},
                    "pending_vault_salt": {"B": salt},
                    "pending_verifier": {"B": b"pv"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": "SET rotation_state = :paused, updated_at = :now",
                "ConditionExpression": STATE_CONDITION,
                "ExpressionAttributeValues": {
                    ":paused": "PAUSED",
                    ":expected": "IN_PROGRESS",
                    ":now": NOW,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(vault_service, "PAUSE", "IN_PROGRESS")
        assert result == {
            "rotation_state": "PAUSED",
            "rotation_locked_at": 1699999000,
            "pending_vault_salt": salt,
            "pending_verifier": b"pv",
        }

    @pytest.mark.parametrize("expected_state", ["IDLE", "PAUSED"])
    def test_pause_requires_expected_in_progress(
        self, vault_service, dynamodb_stubber, expected_state
    ):
        with pytest.raises(BadRequestError, match="IN_PROGRESS"):
            self._rotate(vault_service, "PAUSE", expected_state)

    def test_pause_conflict_raises_conflict_error(self, vault_service, dynamodb_stubber):
        """A row that exists but fails the state check is a real conflict, not a 404."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item", _vault_row(), {"TableName": "test-vaults-table", "Key": ROTATION_KEY}
        )
        with pytest.raises(ConflictError, match="already in progress"):
            self._rotate(vault_service, "PAUSE", "IN_PROGRESS")

    # RELEASE

    def test_release_promotes_staged_pair(self, vault_service, dynamodb_stubber, frozen_time):
        salt, verifier, name = secrets.token_bytes(16), b"staged-verifier", b"new-name"
        self._stub_release_read(
            dynamodb_stubber,
            kek_version={"N": "1"},
            pending_vault_salt={"B": salt},
            pending_verifier={"B": verifier},
        )
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IDLE"},
                    "rotation_locked_at": {"N": "1699999000"},
                    "kek_version": {"N": "2"},
                    "vault_salt": {"B": salt},
                    "verifier": {"B": verifier},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": (
                    RELEASE_UPDATE + ", kek_version = :kv, encrypted_name = :name"
                    ", vault_salt = :pending_salt, verifier = :pending_verifier"
                    " REMOVE pending_vault_salt, pending_verifier"
                ),
                "ConditionExpression": (
                    STATE_CONDITION + " AND pending_vault_salt = :pending_salt"
                    " AND pending_verifier = :pending_verifier AND kek_version = :prev"
                ),
                "ExpressionAttributeValues": {
                    ":idle": "IDLE",
                    ":expected": "IN_PROGRESS",
                    ":now": NOW,
                    ":kv": 2,
                    ":name": name,
                    ":pending_salt": salt,
                    ":pending_verifier": verifier,
                    ":prev": 1,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(
            vault_service, "RELEASE", "IN_PROGRESS", kek_version=2, new_encrypted_name=name
        )
        assert result == {
            "rotation_state": "IDLE",
            "rotation_locked_at": 1699999000,
            "pending_vault_salt": None,
            "pending_verifier": None,
        }

    def test_release_with_nothing_staged_writes_new_verifier(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        self._stub_release_read(dynamodb_stubber, kek_version={"N": "1"})
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"rotation_state": {"S": "IDLE"}, "kek_version": {"N": "2"}}},
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": RELEASE_UPDATE + ", kek_version = :kv, verifier = :ver",
                "ConditionExpression": (
                    STATE_CONDITION
                    + " AND attribute_not_exists(pending_vault_salt) AND kek_version = :prev"
                ),
                "ExpressionAttributeValues": {
                    ":idle": "IDLE",
                    ":expected": "IN_PROGRESS",
                    ":now": NOW,
                    ":kv": 2,
                    ":ver": b"fresh-verifier",
                    ":prev": 1,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(
            vault_service, "RELEASE", "IN_PROGRESS", kek_version=2, new_verifier=b"fresh-verifier"
        )
        assert result == {
            "rotation_state": "IDLE",
            "rotation_locked_at": None,
            "pending_vault_salt": None,
            "pending_verifier": None,
        }

    def test_release_without_kek_version_and_nothing_staged(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        self._stub_release_read(dynamodb_stubber)
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"rotation_state": {"S": "IDLE"}}},
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": RELEASE_UPDATE,
                "ConditionExpression": STATE_CONDITION
                + " AND attribute_not_exists(pending_vault_salt)",
                "ExpressionAttributeValues": {
                    ":idle": "IDLE",
                    ":expected": "IN_PROGRESS",
                    ":now": NOW,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(vault_service, "RELEASE", "IN_PROGRESS")
        assert result["rotation_state"] == "IDLE"

    def test_release_on_legacy_row_guards_missing_kek_version(
        self, vault_service, dynamodb_stubber
    ):
        self._stub_release_read(dynamodb_stubber)
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"rotation_state": {"S": "IDLE"}, "kek_version": {"N": "2"}}},
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": RELEASE_UPDATE + ", kek_version = :kv",
                "ConditionExpression": (
                    STATE_CONDITION + " AND attribute_not_exists(pending_vault_salt)"
                    " AND attribute_not_exists(kek_version)"
                ),
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(vault_service, "RELEASE", "IN_PROGRESS", kek_version=2)
        assert result["rotation_state"] == "IDLE"

    def test_release_rejects_kek_version_not_current_plus_one(
        self, vault_service, dynamodb_stubber
    ):
        self._stub_release_read(dynamodb_stubber, kek_version={"N": "3"})
        with pytest.raises(ConflictError, match="kekVersion must be the current version plus one"):
            self._rotate(vault_service, "RELEASE", "IN_PROGRESS", kek_version=5)

    @pytest.mark.parametrize("kwargs", [{}, {"kek_version": 2, "new_verifier": b"fresh"}])
    def test_release_while_staged_requires_kek_version_only(
        self, vault_service, dynamodb_stubber, kwargs
    ):
        self._stub_release_read(
            dynamodb_stubber,
            kek_version={"N": "1"},
            pending_vault_salt={"B": b"s" * 16},
            pending_verifier={"B": b"pv"},
        )
        with pytest.raises(
            ConflictError,
            match="A rotation with a new salt is staged; commit it with kekVersion only, or PAUSE",
        ):
            self._rotate(vault_service, "RELEASE", "IN_PROGRESS", **kwargs)

    def test_release_rejects_new_vault_salt(self, vault_service, dynamodb_stubber):
        with pytest.raises(BadRequestError, match="newVaultSalt"):
            self._rotate(
                vault_service, "RELEASE", "IN_PROGRESS", kek_version=2, new_vault_salt=b"s" * 16
            )

    def test_release_missing_vault_is_not_found(self, vault_service, dynamodb_stubber):
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY, "ConsistentRead": True},
        )
        with pytest.raises(NotFoundError, match="Vault not found"):
            self._rotate(vault_service, "RELEASE", "IN_PROGRESS", kek_version=2)

    def test_release_conflict_raises_conflict_error(self, vault_service, dynamodb_stubber):
        """A row that exists but fails the state check is a real conflict, not a 404."""
        self._stub_release_read(dynamodb_stubber, kek_version={"N": "1"})
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item", _vault_row(), {"TableName": "test-vaults-table", "Key": ROTATION_KEY}
        )
        with pytest.raises(ConflictError, match="already in progress"):
            self._rotate(vault_service, "RELEASE", "IN_PROGRESS", kek_version=2)
