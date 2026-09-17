"""
Unit tests for vault route handlers.

Tests verify that vault routes work correctly through the FastAPI test client.
Uses botocore Stubber for AWS service testing (not mocking).
"""

import base64
import json
import secrets
import time

import pytest
from botocore.stub import ANY

from tests.fixtures.vault_deletion import (
    ITEMS_TABLE,
    SHARES_TABLE,
    collection_row,
    item_key,
    media_row,
    s3_key_for,
    share_key,
    share_row,
    stub_batch_delete,
    stub_collections_page,
    stub_empty_tail,
    stub_items_page,
    stub_mark,
    stub_mark_condition_failed,
    stub_purge,
    stub_row_delete,
    stub_s3_delete,
    stub_shares_page,
    vault_row,
)


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

    def test_create_vault_route_handler_accepts_no_body(self, client, dynamodb_stubber):
        """Test create vault route handler no longer requires a request body."""
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )

        response = client.post("/v1/vaults")

        assert response.status_code == 200
        body = response.json()
        assert "vaultId" in body
        assert "vaultSalt" in body


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
        # Nothing stored or staged on this row: the optional blobs are null.
        assert body["encryptedName"] is None
        assert body["verifier"] is None
        assert body["pendingVaultSalt"] is None
        assert body["pendingVerifier"] is None

    def test_get_vault_returns_verifier_and_staged_pair(self, client, dynamodb_stubber):
        user_id = "test-user-id"
        vault_id = "test-vault-1"
        encrypted_name = secrets.token_bytes(40)
        verifier = secrets.token_bytes(48)
        pending_salt = secrets.token_bytes(16)
        pending_verifier = secrets.token_bytes(48)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": vault_row(
                    user_id,
                    vault_id,
                    encrypted_name={"B": encrypted_name},
                    verifier={"B": verifier},
                    pending_vault_salt={"B": pending_salt},
                    pending_verifier={"B": pending_verifier},
                    updated_at={"N": "1700000500"},
                    kek_version={"N": "1"},
                    rotation_state={"S": "IN_PROGRESS"},
                    rotation_locked_at={"N": "1700000500"},
                )
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )
        response = client.get(f"/v1/vaults/{vault_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["rotationState"] == "IN_PROGRESS"
        assert body["rotationLockedAt"] == 1700000500
        assert base64.b64decode(body["encryptedName"]) == encrypted_name
        assert base64.b64decode(body["verifier"]) == verifier
        assert base64.b64decode(body["pendingVaultSalt"]) == pending_salt
        assert base64.b64decode(body["pendingVerifier"]) == pending_verifier


class TestUpdateVaultRotationRoute:
    def test_acquire_rotation_lock(self, client, dynamodb_stubber):
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
        # The service disambiguates the failed condition with one get_item; a row
        # that exists but fails the state check is a real conflict, not a 404.
        dynamodb_stubber.add_response(
            "get_item",
            {"Item": vault_row(user_id="test-user-id", vault_id=vault_id)},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "ACQUIRE", "expectedState": "IDLE"},
        )
        assert response.status_code == 409

    def test_acquire_unknown_vault_returns_404(self, client, dynamodb_stubber):
        """A retried ACQUIRE against a vault deleted from another device 404s."""
        vault_id = "test-vault-1"
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "ACQUIRE", "expectedState": "IDLE"},
        )
        assert response.status_code == 404

    def test_pause_returns_paused(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "PAUSED"},
                    "rotation_locked_at": {"N": "1700000500"},
                    "pending_vault_salt": {"B": b"\x01" * 16},
                    "pending_verifier": {"B": b"\x02" * 48},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
                "UpdateExpression": "SET rotation_state = :paused, updated_at = :now",
                "ConditionExpression": (
                    "attribute_not_exists(deletion_state) AND rotation_state = :expected"
                ),
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "PAUSE", "expectedState": "IN_PROGRESS"},
        )
        assert response.status_code == 200
        assert response.json()["rotationState"] == "PAUSED"

    def test_acquire_with_salt_and_verifier_returns_staged_pair(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        # The row already holds a pair staged by an earlier attempt; if_not_exists
        # keeps it, and ALL_NEW hands that pair back, not the one we sent.
        staged_salt = secrets.token_bytes(16)
        staged_verifier = secrets.token_bytes(48)
        sent_salt = secrets.token_bytes(16)
        sent_verifier = secrets.token_bytes(48)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": "1700000500"},
                    "pending_vault_salt": {"B": staged_salt},
                    "pending_verifier": {"B": staged_verifier},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
                "UpdateExpression": (
                    "SET rotation_state = :in_progress, rotation_locked_at = :now, "
                    "updated_at = :now, "
                    "pending_vault_salt = if_not_exists(pending_vault_salt, :salt), "
                    "pending_verifier = if_not_exists(pending_verifier, :pv)"
                    " ADD rotation_generation :one"
                ),
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={
                "action": "ACQUIRE",
                "expectedState": "IDLE",
                "newVaultSalt": base64.b64encode(sent_salt).decode("utf-8"),
                "newVerifier": base64.b64encode(sent_verifier).decode("utf-8"),
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rotationState"] == "IN_PROGRESS"
        assert base64.b64decode(body["pendingVaultSalt"]) == staged_salt
        assert base64.b64decode(body["pendingVerifier"]) == staged_verifier

    @pytest.mark.parametrize("field", ["newVaultSalt", "newVerifier"])
    def test_acquire_with_only_one_of_the_pair_returns_400(self, client, dynamodb_stubber, field):
        # No DynamoDB stub: the service must reject before any write.
        vault_id = "test-vault-1"
        blob = base64.b64encode(secrets.token_bytes(16)).decode("utf-8")
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "ACQUIRE", "expectedState": "IDLE", field: blob},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"

    def test_acquire_rejects_salt_that_is_not_16_bytes(self, client):
        # Smithy @length(min: 16, max: 16) on newVaultSalt: pydantic rejects it as 422.
        response = client.post(
            "/v1/vaults/test-vault-1/rotation",
            json={
                "action": "ACQUIRE",
                "expectedState": "IDLE",
                "newVaultSalt": base64.b64encode(b"\x01" * 15).decode("utf-8"),
                "newVerifier": base64.b64encode(b"\x02" * 48).decode("utf-8"),
            },
        )
        assert response.status_code == 422

    def _stub_consistent_read(self, dynamodb_stubber, vault_id, item_extra):
        item = vault_row(
            "test-user-id",
            vault_id,
            kek_version={"N": "1"},
            rotation_state={"S": "IN_PROGRESS"},
            rotation_locked_at={"N": "1700000500"},
            **item_extra,
        )
        dynamodb_stubber.add_response(
            "get_item",
            {"Item": item},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
                "ConsistentRead": True,
            },
        )

    def test_release_staged_with_kek_version_and_name(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        pending_salt = secrets.token_bytes(16)
        pending_verifier = secrets.token_bytes(48)
        new_name = secrets.token_bytes(40)
        self._stub_consistent_read(
            dynamodb_stubber,
            vault_id,
            {
                "pending_vault_salt": {"B": pending_salt},
                "pending_verifier": {"B": pending_verifier},
            },
        )
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IDLE"},
                    "rotation_locked_at": {"N": "1700000500"},
                    "kek_version": {"N": "2"},
                    "vault_salt": {"B": pending_salt},
                    "verifier": {"B": pending_verifier},
                    "encrypted_name": {"B": new_name},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
                "UpdateExpression": (
                    "SET rotation_state = :idle, updated_at = :now, kek_version = :kv, "
                    "encrypted_name = :name, "
                    "vault_salt = :pending_salt, verifier = :pending_verifier "
                    "REMOVE pending_vault_salt, pending_verifier"
                ),
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={
                "action": "RELEASE",
                "expectedState": "IN_PROGRESS",
                "kekVersion": 2,
                "newEncryptedName": base64.b64encode(new_name).decode("utf-8"),
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["rotationState"] == "IDLE"
        assert body["pendingVaultSalt"] is None
        assert body["pendingVerifier"] is None

    def test_release_staged_without_kek_version_returns_409(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        self._stub_consistent_read(
            dynamodb_stubber,
            vault_id,
            {
                "pending_vault_salt": {"B": secrets.token_bytes(16)},
                "pending_verifier": {"B": secrets.token_bytes(48)},
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={"action": "RELEASE", "expectedState": "IN_PROGRESS"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["message"] == (
            "A rotation with a new salt is staged; commit it with kekVersion only, or PAUSE"
        )

    def test_release_staged_with_new_verifier_returns_409(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        self._stub_consistent_read(
            dynamodb_stubber,
            vault_id,
            {
                "pending_vault_salt": {"B": secrets.token_bytes(16)},
                "pending_verifier": {"B": secrets.token_bytes(48)},
            },
        )
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={
                "action": "RELEASE",
                "expectedState": "IN_PROGRESS",
                "kekVersion": 2,
                "newVerifier": base64.b64encode(secrets.token_bytes(48)).decode("utf-8"),
            },
        )
        assert response.status_code == 409
        assert response.json()["error"]["message"] == (
            "A rotation with a new salt is staged; commit it with kekVersion only, or PAUSE"
        )

    def test_release_with_new_vault_salt_returns_400(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        # No DynamoDB stub: the service rejects newVaultSalt before its consistent read
        # (Task 3), so any DynamoDB call fails this test.
        response = client.post(
            f"/v1/vaults/{vault_id}/rotation",
            json={
                "action": "RELEASE",
                "expectedState": "IN_PROGRESS",
                "kekVersion": 2,
                "newVaultSalt": base64.b64encode(secrets.token_bytes(16)).decode("utf-8"),
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"


class TestAbandonRotationRoute:
    """ABANDON dispatches to RotationAbandonService, not VaultService (spec 5)."""

    VAULT_ID = "test-vault-1"
    KEY = {"PK": "USER#test-user-id", "SK": "VAULT#test-vault-1"}

    def _stub_paused_vault(self, dynamodb_stubber, kek_version=1):
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": vault_row(
                    "test-user-id",
                    self.VAULT_ID,
                    rotation_state={"S": "PAUSED"},
                    pending_vault_salt={"B": b"\x01" * 16},
                    pending_verifier={"B": b"\x02" * 32},
                    kek_version={"N": str(kek_version)},
                )
            },
            {"TableName": "test-vaults-table", "Key": self.KEY},
        )

    def _stub_empty_item_page(self, dynamodb_stubber, kek_version=1):
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": "GSI2PK = :pk",
                "FilterExpression": "dek_version > :kek",
                "ExpressionAttributeValues": {
                    ":pk": f"VAULT#{self.VAULT_ID}",
                    ":kek": kek_version,
                },
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )

    def _stub_empty_collections_page(self, dynamodb_stubber, kek_version=1):
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            {
                "TableName": "test-collections-table",
                "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
                "FilterExpression": "metadata_version > :kek",
                "ExpressionAttributeValues": {
                    ":pk": f"VAULT#{self.VAULT_ID}",
                    ":sk_prefix": "COLLECTION#",
                    ":kek": kek_version,
                },
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )

    def _stub_abandon_write(self, dynamodb_stubber):
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"rotation_state": {"S": "IDLE"}}},
            {
                "TableName": "test-vaults-table",
                "Key": self.KEY,
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

    def test_abandon_returns_200_with_pending_fields_absent(self, client, dynamodb_stubber):
        self._stub_paused_vault(dynamodb_stubber)
        self._stub_empty_item_page(dynamodb_stubber)
        self._stub_empty_collections_page(dynamodb_stubber)
        self._stub_abandon_write(dynamodb_stubber)

        response = client.post(
            f"/v1/vaults/{self.VAULT_ID}/rotation",
            json={"action": "ABANDON", "expectedState": "PAUSED"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["rotationState"] == "IDLE"
        assert body.get("pendingVaultSalt") is None
        assert body.get("pendingVerifier") is None

    def test_abandon_wrong_expected_state_returns_400_with_no_stubs(self, client, dynamodb_stubber):
        # No DynamoDB stub: the route rejects before any I/O.
        response = client.post(
            f"/v1/vaults/{self.VAULT_ID}/rotation",
            json={"action": "ABANDON", "expectedState": "IN_PROGRESS"},
        )

        assert response.status_code == 400
        assert response.json()["error"]["message"] == "ABANDON requires expectedState PAUSED"

    def test_abandon_conflict_propagates_409(self, client, dynamodb_stubber):
        self._stub_paused_vault(dynamodb_stubber)
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "ITEM#i1"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "i1"},
                        "vault_id": {"S": self.VAULT_ID},
                        "dek_version": {"N": "2"},
                    }
                ]
            },
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": "GSI2PK = :pk",
                "FilterExpression": "dek_version > :kek",
                "ExpressionAttributeValues": {":pk": f"VAULT#{self.VAULT_ID}", ":kek": 1},
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )
        # No collections query and no update_item are stubbed.

        response = client.post(
            f"/v1/vaults/{self.VAULT_ID}/rotation",
            json={"action": "ABANDON", "expectedState": "PAUSED"},
        )

        assert response.status_code == 409


class TestListVaultsRoute:
    """Test suite for ListVaultsRoute through FastAPI test client."""

    def test_list_vaults_returns_page_and_next_token(self, client, dynamodb_stubber):
        user_id = "test-user-id"
        salt_a = secrets.token_bytes(16)
        salt_b = secrets.token_bytes(16)
        name_a = secrets.token_bytes(40)
        verifier_a = secrets.token_bytes(48)
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {"S": "VAULT#vault-a"},
                        "vault_id": {"S": "vault-a"},
                        "user_id": {"S": user_id},
                        "vault_salt": {"B": salt_a},
                        "encrypted_name": {"B": name_a},
                        "verifier": {"B": verifier_a},
                        "created_at": {"N": "1700000000"},
                        "updated_at": {"N": "1700000900"},
                        "kek_version": {"N": "2"},
                        "rotation_state": {"S": "PAUSED"},
                    },
                    {
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {"S": "VAULT#vault-b"},
                        "vault_id": {"S": "vault-b"},
                        "user_id": {"S": user_id},
                        "vault_salt": {"B": salt_b},
                        "created_at": {"N": "1700001000"},
                        "updated_at": {"N": "1700001000"},
                        "kek_version": {"N": "1"},
                        "rotation_state": {"S": "IDLE"},
                    },
                ],
                "LastEvaluatedKey": {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "VAULT#vault-b"}},
            },
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": "attribute_not_exists(deletion_state)",
                "Limit": 50,
            },
        )

        response = client.get("/v1/vaults")

        assert response.status_code == 200
        body = response.json()
        assert [v["vaultId"] for v in body["vaults"]] == ["vault-a", "vault-b"]
        first, second = body["vaults"]
        assert base64.b64decode(first["vaultSalt"]) == salt_a
        assert base64.b64decode(first["encryptedName"]) == name_a
        assert base64.b64decode(first["verifier"]) == verifier_a
        assert first["kekVersion"] == 2
        assert first["rotationState"] == "PAUSED"
        assert first["createdAt"] == 1700000000
        assert first["updatedAt"] == 1700000900
        assert second["encryptedName"] is None
        assert second["verifier"] is None
        assert second["kekVersion"] == 1
        assert second["rotationState"] == "IDLE"
        # The token is the base64 JSON of LastEvaluatedKey.
        assert json.loads(base64.b64decode(body["nextToken"])) == {
            "PK": f"USER#{user_id}",
            "SK": "VAULT#vault-b",
        }

    def test_list_vaults_second_page_passes_exclusive_start_key(self, client, dynamodb_stubber):
        user_id = "test-user-id"
        start_key = {"PK": f"USER#{user_id}", "SK": "VAULT#vault-b"}
        token = base64.b64encode(json.dumps(start_key).encode("utf-8")).decode("utf-8")
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": "attribute_not_exists(deletion_state)",
                "Limit": 10,
                "ExclusiveStartKey": start_key,
            },
        )

        response = client.get("/v1/vaults", params={"pageSize": 10, "nextToken": token})

        assert response.status_code == 200
        assert response.json() == {"vaults": [], "nextToken": None}

    def test_list_vaults_empty_filtered_page_keeps_next_token(self, client, dynamodb_stubber):
        # DynamoDB applies Limit before FilterExpression: a page whose only row was a
        # DELETING vault comes back empty but with a LastEvaluatedKey. The route must
        # surface the token so the client keeps paging.
        user_id = "test-user-id"
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [],
                "Count": 0,
                "ScannedCount": 1,
                "LastEvaluatedKey": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": "VAULT#deleting-vault"},
                },
            },
            {
                "TableName": "test-vaults-table",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": "attribute_not_exists(deletion_state)",
                "Limit": 50,
            },
        )

        response = client.get("/v1/vaults")

        assert response.status_code == 200
        body = response.json()
        assert body["vaults"] == []
        assert body["nextToken"] is not None

    def test_list_vaults_rejects_page_size_below_ten(self, client):
        response = client.get("/v1/vaults", params={"pageSize": 5})
        assert response.status_code == 422

    def test_list_vaults_rejects_next_token_over_1024_chars(self, client):
        # Smithy @length(max: 1024) on nextToken (spec 3.3).
        response = client.get("/v1/vaults", params={"nextToken": "a" * 1025})
        assert response.status_code == 422


class TestUpdateVaultRoute:
    """Test suite for UpdateVaultRoute through FastAPI test client."""

    UPDATE_CONDITION = "attribute_exists(PK) AND attribute_not_exists(deletion_state)"

    def test_update_vault_name_only(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        encrypted_name = secrets.token_bytes(40)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "vault_id": {"S": vault_id},
                    "updated_at": {"N": "1700000100"},
                    "encrypted_name": {"B": encrypted_name},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
                "UpdateExpression": "SET updated_at = :now, encrypted_name = :name",
                "ConditionExpression": self.UPDATE_CONDITION,
                "ExpressionAttributeValues": ANY,
            },
        )

        response = client.put(
            f"/v1/vaults/{vault_id}",
            json={"encryptedName": base64.b64encode(encrypted_name).decode("utf-8")},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["vaultId"] == vault_id
        assert isinstance(body["updatedAt"], (int, float))

    def test_update_vault_verifier_only(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        verifier = secrets.token_bytes(48)
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"vault_id": {"S": vault_id}, "updated_at": {"N": "1700000100"}}},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
                "UpdateExpression": "SET updated_at = :now, verifier = :ver",
                "ConditionExpression": self.UPDATE_CONDITION,
                "ExpressionAttributeValues": ANY,
            },
        )

        response = client.put(
            f"/v1/vaults/{vault_id}",
            json={"verifier": base64.b64encode(verifier).decode("utf-8")},
        )

        assert response.status_code == 200
        assert response.json()["vaultId"] == vault_id

    def test_update_vault_empty_body_returns_400(self, client):
        # No stub: the route rejects before touching DynamoDB.
        response = client.put("/v1/vaults/test-vault-1", json={})

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "BAD_REQUEST"
        assert body["error"]["message"] == "Provide encryptedName or verifier"

    def test_update_vault_missing_vault_returns_404(self, client, dynamodb_stubber):
        vault_id = "nonexistent-vault"
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        # The service disambiguates the failed condition with one get_item: no row -> 404.
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.put(
            f"/v1/vaults/{vault_id}",
            json={"encryptedName": base64.b64encode(secrets.token_bytes(40)).decode("utf-8")},
        )

        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Vault not found"

    def test_update_vault_deleting_vault_returns_409(self, client, dynamodb_stubber):
        vault_id = "test-vault-1"
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        # Row exists but carries deletion_state -> 409.
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#test-user-id"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": "test-user-id"},
                    "vault_salt": {"B": b"\xaa" * 16},
                    "created_at": {"N": "1700000000"},
                    "deletion_state": {"S": "DELETING"},
                    "deletion_started_at": {"N": "1700000900"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.put(
            f"/v1/vaults/{vault_id}",
            json={"verifier": base64.b64encode(secrets.token_bytes(48)).decode("utf-8")},
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "CONFLICT"


class TestDeleteVaultRoute:
    """DELETE /v1/vaults/{vault_id}: one bounded, resumable deletion step per call."""

    USER = "test-user-id"  # the user the `client` fixture authenticates as
    VAULT = "vault-to-delete"

    def test_live_rotation_lock_returns_409(self, client, dynamodb_stubber):
        locked = vault_row(
            self.USER,
            self.VAULT,
            rotation_state={"S": "IN_PROGRESS"},
            rotation_locked_at={"N": str(int(time.time()))},
        )
        stub_mark_condition_failed(dynamodb_stubber, self.USER, self.VAULT, locked)

        response = client.delete(f"/v1/vaults/{self.VAULT}")

        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "CONFLICT"
        assert body["error"]["message"] == (
            "A vault password change is in progress; wait for it to finish or pause it first"
        )

    def test_paused_vault_is_deleted_in_one_call(self, client, dynamodb_stubber):
        stub_mark(dynamodb_stubber, self.USER, self.VAULT, rotation_state="PAUSED")
        stub_empty_tail(dynamodb_stubber, self.USER, self.VAULT)
        stub_row_delete(dynamodb_stubber, self.USER, self.VAULT)

        response = client.delete(f"/v1/vaults/{self.VAULT}")

        assert response.status_code == 200
        assert response.json() == {
            "deletionState": "DELETED",
            "deletedItems": 0,
            "deletedCollections": 0,
            "deletedShares": 0,
        }

    def test_two_call_progression_ends_with_404(self, client, dynamodb_stubber, s3_stubber):
        stub_mark(dynamodb_stubber, self.USER, self.VAULT)
        stub_items_page(dynamodb_stubber, self.VAULT, [media_row("m1", self.VAULT, self.USER)])
        stub_s3_delete(s3_stubber, s3_key_for(self.VAULT, "m1"))
        stub_batch_delete(dynamodb_stubber, ITEMS_TABLE, [item_key("m1")])
        stub_items_page(dynamodb_stubber, self.VAULT, [])
        stub_collections_page(
            dynamodb_stubber, self.VAULT, [collection_row("c1", self.VAULT, self.USER)]
        )
        stub_purge(dynamodb_stubber, self.VAULT, "c1", ["m1"], self.USER)
        stub_collections_page(dynamodb_stubber, self.VAULT, [])
        stub_shares_page(
            dynamodb_stubber, self.USER, self.VAULT, [share_row("s1", self.VAULT, self.USER)]
        )
        stub_batch_delete(dynamodb_stubber, SHARES_TABLE, [share_key("s1")])
        stub_row_delete(dynamodb_stubber, self.USER, self.VAULT)

        first = client.delete(f"/v1/vaults/{self.VAULT}")

        assert first.status_code == 200
        assert first.json() == {
            "deletionState": "DELETED",
            "deletedItems": 1,
            "deletedCollections": 1,
            "deletedShares": 1,
        }

        stub_mark_condition_failed(dynamodb_stubber, self.USER, self.VAULT, None)

        second = client.delete(f"/v1/vaults/{self.VAULT}")

        assert second.status_code == 404
        assert "not found" in second.json()["error"]["message"].lower()
