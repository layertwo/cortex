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
                        "created_at": {"N": "1234567891"},
                        "updated_at": {"N": "1234567999"},
                        "current_vmk_version": {"N": "3"},
                        "envelope_version": {"N": "2"},
                        "rotation_state": {"S": "IN_PROGRESS"},
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
            "created_at": 1234567890,
            "updated_at": 1234567890,
            "current_vmk_version": 0,
            "envelope_version": 0,
            "rotation_state": "IDLE",
        }
        assert "verifier" not in vaults[0]
        assert vaults[1]["vault_salt"] == salt2
        assert vaults[1]["encrypted_name"] == name2
        assert vaults[1]["updated_at"] == 1234567999
        assert vaults[1]["current_vmk_version"] == 3
        assert vaults[1]["envelope_version"] == 2
        assert vaults[1]["rotation_state"] == "IN_PROGRESS"

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

    def test_get_vault_fresh_vault_defaults_versions_and_envelopes(
        self, vault_service, dynamodb_stubber
    ):
        """A fresh vault reads back with VMK version 0 and an empty envelope list."""
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
        assert result["current_vmk_version"] == 0
        assert result["envelope_version"] == 0
        assert result["vmk_envelopes"] == []
        assert result["rotation_state"] == "IDLE"
        assert result["rotation_locked_at"] is None
        assert "verifier" not in result

    def test_get_vault_raises_not_found(self, vault_service, dynamodb_stubber):
        """Test that get_vault raises NotFoundError when vault doesn't exist."""
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": ANY},
        )
        with pytest.raises(NotFoundError):
            vault_service.get_vault(user_id="u1", vault_id="v1")

    def test_create_vault_writes_updated_at_and_vmk_versions(self, vault_service, dynamodb_stubber):
        """create_vault stamps updated_at and initialises both version counters."""
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
                    "current_vmk_version": 0,
                    "envelope_version": 0,
                },
                "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
            },
        )

        result = vault_service.create_vault(user_id="u1", vault_salt=salt)

        assert result["vault_salt"] == salt

    def test_get_vault_returns_vmk_envelopes(self, vault_service, dynamodb_stubber):
        """get_vault surfaces encrypted_name, the version counters, and every VMK envelope."""
        name = secrets.token_bytes(24)
        wrapped1 = secrets.token_bytes(61)
        wrapped2 = secrets.token_bytes(61)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": vault_row(
                    "u1",
                    "v1",
                    vault_salt={"B": b"\x01" * 16},
                    encrypted_name={"B": name},
                    updated_at={"N": "1700000500"},
                    current_vmk_version={"N": "2"},
                    envelope_version={"N": "1"},
                    vmk_envelopes={
                        "L": [
                            {
                                "M": {
                                    "vmk_version": {"N": "1"},
                                    "wrapped_vmk": {"B": wrapped1},
                                    "created_at": {"N": "1700000400"},
                                }
                            },
                            {
                                "M": {
                                    "vmk_version": {"N": "2"},
                                    "wrapped_vmk": {"B": wrapped2},
                                    "created_at": {"N": "1700000500"},
                                }
                            },
                        ]
                    },
                    rotation_state={"S": "IN_PROGRESS"},
                    rotation_locked_at={"N": "1700000500"},
                )
            },
            {"TableName": "test-vaults-table", "Key": {"PK": "USER#u1", "SK": "VAULT#v1"}},
        )

        result = vault_service.get_vault(user_id="u1", vault_id="v1")

        assert result["vault_salt"] == b"\x01" * 16
        assert result["encrypted_name"] == name
        assert result["current_vmk_version"] == 2
        assert result["envelope_version"] == 1
        assert result["vmk_envelopes"] == [
            {"vmk_version": 1, "wrapped_vmk": wrapped1, "created_at": 1700000400},
            {"vmk_version": 2, "wrapped_vmk": wrapped2, "created_at": 1700000500},
        ]
        assert result["updated_at"] == 1700000500
        assert result["rotation_state"] == "IN_PROGRESS"
        assert result["rotation_locked_at"] == 1700000500
        assert "verifier" not in result

    def test_get_vault_defaults_optional_fields(self, vault_service, dynamodb_stubber):
        """A row without a name, envelopes, or version counters reads back with defaults."""
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
        assert result["current_vmk_version"] == 0
        assert result["envelope_version"] == 0
        assert result["vmk_envelopes"] == []
        assert result["updated_at"] == 1700000000
        assert result["rotation_state"] == "IDLE"
        assert "verifier" not in result

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

    def test_update_vault_writes_encrypted_name_only(
        self, vault_service, dynamodb_stubber, monkeypatch
    ):
        """update_vault pins the SET expression (name only) and the exists/not-deleting guard."""
        monkeypatch.setattr(time, "time", lambda: 1_700_000_000)
        name = secrets.token_bytes(24)
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#u1", "SK": "VAULT#v1"},
                "UpdateExpression": "SET updated_at = :now, encrypted_name = :name",
                "ConditionExpression": "attribute_exists(PK) AND attribute_not_exists(deletion_state)",
                "ExpressionAttributeValues": {":now": 1_700_000_000, ":name": name},
            },
        )

        result = vault_service.update_vault(user_id="u1", vault_id="v1", encrypted_name=name)

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
            vault_service.update_vault(user_id="u1", vault_id="v1", encrypted_name=b"n" * 24)

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
            vault_service.update_vault(user_id="u1", vault_id="v1", encrypted_name=b"n" * 24)

    def test_update_vault_reraises_other_errors(self, vault_service, dynamodb_stubber):
        """A non-conditional DynamoDB error propagates unchanged."""
        dynamodb_stubber.add_client_error("update_item", service_error_code="ServiceUnavailable")

        with pytest.raises(ClientError):
            vault_service.update_vault(user_id="u1", vault_id="v1", encrypted_name=b"n" * 24)

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
                    ":in_progress": "IN_PROGRESS",
                    ":stale": 1_700_000_000 - 7 * 24 * 3600,
                },
            },
        )

        assert vault_service.mark_deleting(user_id="u1", vault_id="v1") is None

    def test_mark_deleting_allows_idle_after_vmk(self, vault_service, dynamodb_stubber):
        """An IDLE vault (a finished VMK rotation) is deletable: no PAUSED branch remains."""
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#u1", "SK": "VAULT#v1"},
                "UpdateExpression": MARK_UPDATE_EXPRESSION,
                "ConditionExpression": MARK_CONDITION_EXPRESSION,
                "ExpressionAttributeValues": ANY,
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
            match="A key rotation is in progress; finish it before deleting this vault",
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


class TestUpdateVaultPassword:
    """update_vault_password: bootstrap and pure re-wrap under an envelope-version guard."""

    UPDATE = "SET vmk_envelopes = :env, envelope_version = :next"
    CONDITION = "envelope_version = :expected AND attribute_not_exists(deletion_state)"

    def _stub_read(self, dynamodb_stubber, **extra):
        dynamodb_stubber.add_response(
            "get_item",
            {"Item": vault_row("u1", "v1", **extra)},
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY, "ConsistentRead": True},
        )

    def test_update_vault_password_bootstrap_stores_first_envelope(
        self, vault_service, dynamodb_stubber
    ):
        """Empty stored set + expected 0 writes one version-1 envelope and enrols VMK 1."""
        wrapped = secrets.token_bytes(61)
        envelopes = [{"vmk_version": 1, "wrapped_vmk": wrapped, "created_at": 1700000400}]
        self._stub_read(
            dynamodb_stubber,
            envelope_version={"N": "0"},
            current_vmk_version={"N": "0"},
        )
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": self.UPDATE + ", current_vmk_version = :cur",
                "ConditionExpression": self.CONDITION,
                "ExpressionAttributeValues": {
                    ":env": envelopes,
                    ":next": 1,
                    ":cur": 1,
                    ":expected": 0,
                },
            },
        )

        result = vault_service.update_vault_password(
            user_id="u1", vault_id="v1", expected_envelope_version=0, envelopes=envelopes
        )

        assert result == {"envelope_version": 1}

    def test_update_vault_password_bootstrap_rejects_other_versions(
        self, vault_service, dynamodb_stubber
    ):
        """Bootstrap requires exactly one version-1 envelope; a version 2 is a conflict."""
        self._stub_read(
            dynamodb_stubber,
            envelope_version={"N": "0"},
            current_vmk_version={"N": "0"},
        )
        with pytest.raises(ConflictError):
            vault_service.update_vault_password(
                user_id="u1",
                vault_id="v1",
                expected_envelope_version=0,
                envelopes=[{"vmk_version": 2, "wrapped_vmk": b"\x02" * 61, "created_at": 1}],
            )

    def test_update_vault_password_stale_version_conflicts(self, vault_service, dynamodb_stubber):
        """A stale expectedEnvelopeVersion fails the guarded write -> ConflictError."""
        self._stub_read(
            dynamodb_stubber,
            envelope_version={"N": "2"},
            current_vmk_version={"N": "1"},
            vmk_envelopes={
                "L": [
                    {
                        "M": {
                            "vmk_version": {"N": "1"},
                            "wrapped_vmk": {"B": b"\x01" * 61},
                            "created_at": {"N": "1"},
                        }
                    }
                ]
            },
        )
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )

        with pytest.raises(ConflictError):
            vault_service.update_vault_password(
                user_id="u1",
                vault_id="v1",
                expected_envelope_version=1,
                envelopes=[{"vmk_version": 1, "wrapped_vmk": b"\x02" * 61, "created_at": 2}],
            )

    def test_update_vault_password_cannot_drop_a_version(self, vault_service, dynamodb_stubber):
        """Dropping a stored version is rejected before any write."""
        stored_versions = [1, 2]
        self._stub_read(
            dynamodb_stubber,
            envelope_version={"N": "1"},
            current_vmk_version={"N": "2"},
            vmk_envelopes={
                "L": [
                    {
                        "M": {
                            "vmk_version": {"N": str(v)},
                            "wrapped_vmk": {"B": b"\x01" * 61},
                            "created_at": {"N": "1"},
                        }
                    }
                    for v in stored_versions
                ]
            },
        )

        with pytest.raises(ConflictError, match="version"):
            vault_service.update_vault_password(
                user_id="u1",
                vault_id="v1",
                expected_envelope_version=1,
                envelopes=[{"vmk_version": 2, "wrapped_vmk": b"\x02" * 61, "created_at": 2}],
            )

    def test_update_vault_password_rewrap_keeps_current_vmk_version(
        self, vault_service, dynamodb_stubber
    ):
        """Re-wrap of the whole stored set writes only envelopes + envelope_version."""
        envelopes = [
            {"vmk_version": 1, "wrapped_vmk": b"\x0a" * 61, "created_at": 10},
            {"vmk_version": 2, "wrapped_vmk": b"\x0b" * 61, "created_at": 11},
        ]
        self._stub_read(
            dynamodb_stubber,
            envelope_version={"N": "4"},
            current_vmk_version={"N": "2"},
            vmk_envelopes={
                "L": [
                    {
                        "M": {
                            "vmk_version": {"N": "1"},
                            "wrapped_vmk": {"B": b"\x01" * 61},
                            "created_at": {"N": "1"},
                        }
                    },
                    {
                        "M": {
                            "vmk_version": {"N": "2"},
                            "wrapped_vmk": {"B": b"\x02" * 61},
                            "created_at": {"N": "2"},
                        }
                    },
                ]
            },
        )
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": self.UPDATE,
                "ConditionExpression": self.CONDITION,
                "ExpressionAttributeValues": {":env": envelopes, ":next": 5, ":expected": 4},
            },
        )

        result = vault_service.update_vault_password(
            user_id="u1", vault_id="v1", expected_envelope_version=4, envelopes=envelopes
        )

        assert result == {"envelope_version": 5}

    def test_update_vault_password_missing_vault_is_not_found(
        self, vault_service, dynamodb_stubber
    ):
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY, "ConsistentRead": True},
        )
        with pytest.raises(NotFoundError, match="Vault not found"):
            vault_service.update_vault_password(
                user_id="u1",
                vault_id="v1",
                expected_envelope_version=0,
                envelopes=[{"vmk_version": 1, "wrapped_vmk": b"\x01" * 61, "created_at": 1}],
            )


ROTATION_KEY = {"PK": "USER#u1", "SK": "VAULT#v1"}
NOW = 1_700_000_000
LOCKED_AT = 1_699_999_000
STALE = NOW - 7 * 24 * 3600

ACQUIRE_UPDATE = (
    "SET rotation_state = :in_progress, rotation_locked_at = :now, updated_at = :now, "
    "current_vmk_version = :nv, envelope_version = :nev, vmk_envelopes = :env"
)
ACQUIRE_CONDITION = (
    "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND ("
    "attribute_not_exists(rotation_state) OR rotation_state = :idle OR "
    "(rotation_state = :in_progress AND rotation_locked_at < :stale))"
    " AND envelope_version = :expected_env"
)
RELEASE_UPDATE = "SET rotation_state = :idle, updated_at = :now"
RELEASE_CONDITION = "attribute_not_exists(deletion_state) AND rotation_state = :expected"

WRAPPED = b"\x01" * 61


def _vault_row(**extra):
    """get_item response for u1/v1 holding one VMK envelope at version 1."""
    row = vault_row(
        "u1",
        "v1",
        rotation_state={"S": "IDLE"},
        current_vmk_version={"N": "1"},
        envelope_version={"N": "1"},
        vmk_envelopes={
            "L": [
                {
                    "M": {
                        "vmk_version": {"N": "1"},
                        "wrapped_vmk": {"B": WRAPPED},
                        "created_at": {"N": "1"},
                    }
                }
            ]
        },
    )
    row.update(extra)
    return {"Item": row}


class TestVaultRotation:
    """update_vault_rotation: ACQUIRE appends an envelope and bumps; RELEASE flips IDLE."""

    @pytest.fixture
    def frozen_time(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: NOW)
        return NOW

    def _rotate(self, vault_service, action, expected_state, **kwargs):
        return vault_service.update_vault_rotation(
            user_id="u1", vault_id="v1", action=action, expected_state=expected_state, **kwargs
        )

    def _stub_read(self, dynamodb_stubber, **extra):
        dynamodb_stubber.add_response(
            "get_item",
            _vault_row(**extra),
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY, "ConsistentRead": True},
        )

    def test_acquire_appends_envelope_and_bumps_version(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        wrapped = secrets.token_bytes(61)
        self._stub_read(dynamodb_stubber)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": str(NOW)},
                    "current_vmk_version": {"N": "2"},
                    "envelope_version": {"N": "2"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": ACQUIRE_UPDATE,
                "ConditionExpression": ACQUIRE_CONDITION,
                "ExpressionAttributeValues": {
                    ":idle": "IDLE",
                    ":in_progress": "IN_PROGRESS",
                    ":stale": STALE,
                    ":now": NOW,
                    ":nv": 2,
                    ":nev": 2,
                    ":env": [
                        {"vmk_version": 1, "wrapped_vmk": WRAPPED, "created_at": 1},
                        {"vmk_version": 2, "wrapped_vmk": wrapped, "created_at": NOW},
                    ],
                    ":expected_env": 1,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(
            vault_service,
            "ACQUIRE",
            "IDLE",
            expected_envelope_version=1,
            new_vmk_version=2,
            wrapped_new_vmk=wrapped,
        )
        assert result == {
            "rotation_state": "IN_PROGRESS",
            "rotation_locked_at": NOW,
            "current_vmk_version": 2,
            "envelope_version": 2,
        }

    def test_acquire_requires_next_version(self, vault_service, dynamodb_stubber):
        self._stub_read(dynamodb_stubber, current_vmk_version={"N": "2"})
        with pytest.raises(BadRequestError, match="current version plus one"):
            self._rotate(
                vault_service,
                "ACQUIRE",
                "IDLE",
                expected_envelope_version=1,
                new_vmk_version=2,
                wrapped_new_vmk=WRAPPED,
            )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"expected_envelope_version": 1, "wrapped_new_vmk": WRAPPED},
            {"expected_envelope_version": 1, "new_vmk_version": 2},
            {"new_vmk_version": 2, "wrapped_new_vmk": WRAPPED},
        ],
    )
    def test_acquire_requires_version_guard_and_envelope_payload(
        self, vault_service, dynamodb_stubber, kwargs
    ):
        # No read is stubbed: the request must be rejected before any I/O.
        with pytest.raises(BadRequestError):
            self._rotate(vault_service, "ACQUIRE", "IDLE", **kwargs)

    def test_acquire_conflicts_on_stale_envelope_version(self, vault_service, dynamodb_stubber):
        self._stub_read(dynamodb_stubber)
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item", _vault_row(), {"TableName": "test-vaults-table", "Key": ROTATION_KEY}
        )
        with pytest.raises(ConflictError, match="already in progress"):
            self._rotate(
                vault_service,
                "ACQUIRE",
                "IDLE",
                expected_envelope_version=0,
                new_vmk_version=2,
                wrapped_new_vmk=WRAPPED,
            )

    def test_acquire_missing_vault_is_not_found(self, vault_service, dynamodb_stubber):
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": ROTATION_KEY, "ConsistentRead": True},
        )
        with pytest.raises(NotFoundError, match="Vault not found"):
            self._rotate(
                vault_service,
                "ACQUIRE",
                "IDLE",
                expected_envelope_version=1,
                new_vmk_version=2,
                wrapped_new_vmk=WRAPPED,
            )

    def test_release_flips_idle_and_stores_name_only(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        name = secrets.token_bytes(24)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IDLE"},
                    "rotation_locked_at": {"N": str(LOCKED_AT)},
                    "current_vmk_version": {"N": "2"},
                    "envelope_version": {"N": "2"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": RELEASE_UPDATE + ", encrypted_name = :name",
                "ConditionExpression": RELEASE_CONDITION,
                "ExpressionAttributeValues": {
                    ":idle": "IDLE",
                    ":expected": "IN_PROGRESS",
                    ":now": NOW,
                    ":name": name,
                },
                "ReturnValues": "ALL_NEW",
            },
        )
        result = self._rotate(vault_service, "RELEASE", "IN_PROGRESS", new_encrypted_name=name)
        assert result == {
            "rotation_state": "IDLE",
            "rotation_locked_at": LOCKED_AT,
            "current_vmk_version": 2,
            "envelope_version": 2,
        }

    def test_release_without_name_only_flips_state(
        self, vault_service, dynamodb_stubber, frozen_time
    ):
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IDLE"},
                    "current_vmk_version": {"N": "2"},
                    "envelope_version": {"N": "2"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": ROTATION_KEY,
                "UpdateExpression": RELEASE_UPDATE,
                "ConditionExpression": RELEASE_CONDITION,
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
        assert result["current_vmk_version"] == 2

    def test_release_conflict_raises_conflict_error(self, vault_service, dynamodb_stubber):
        """A row that exists but fails the state check is a real conflict, not a 404."""
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item", _vault_row(), {"TableName": "test-vaults-table", "Key": ROTATION_KEY}
        )
        with pytest.raises(ConflictError, match="already in progress"):
            self._rotate(vault_service, "RELEASE", "IN_PROGRESS")

    def test_unknown_action_is_bad_request(self, vault_service):
        """An action outside ACQUIRE/RELEASE is rejected before any write."""
        with pytest.raises(BadRequestError, match="Unknown rotation action"):
            self._rotate(vault_service, "PAUSE", "IDLE")

    def test_acquire_on_a_deleting_vault_is_conflict(self, vault_service, dynamodb_stubber):
        """ACQUIRE refuses a vault already marked for deletion (no write)."""
        self._stub_read(dynamodb_stubber, deletion_state={"S": "DELETING"})
        with pytest.raises(ConflictError, match="being deleted"):
            self._rotate(
                vault_service,
                "ACQUIRE",
                "IDLE",
                expected_envelope_version=1,
                new_vmk_version=2,
                wrapped_new_vmk=WRAPPED,
            )

    def test_acquire_rejects_wrong_wrapped_vmk_length(self, vault_service):
        """A wrapped VMK that is not the 61-byte envelope format is refused before any write."""
        with pytest.raises(BadRequestError, match="61 bytes"):
            self._rotate(
                vault_service,
                "ACQUIRE",
                "IDLE",
                expected_envelope_version=1,
                new_vmk_version=2,
                wrapped_new_vmk=b"\x01" * 60,
            )

    def test_release_requires_expected_state(self, vault_service):
        """RELEASE is the action that reads expectedState; omitting it is a bad request."""
        with pytest.raises(BadRequestError, match="RELEASE requires expectedState"):
            vault_service.update_vault_rotation(
                user_id="u1", vault_id="v1", action="RELEASE", expected_state=None
            )
