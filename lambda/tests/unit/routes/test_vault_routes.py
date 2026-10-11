"""
Unit tests for vault route handlers.

Tests verify that vault routes work correctly through the FastAPI test client.
Uses botocore Stubber for AWS service testing (not mocking).
"""

import base64
import json
import secrets
import time

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
        wrapped = secrets.token_bytes(61)
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
                    "current_vmk_version": {"N": "1"},
                    "envelope_version": {"N": "1"},
                    "vmk_envelopes": {
                        "L": [
                            {
                                "M": {
                                    "vmk_version": {"N": "1"},
                                    "wrapped_vmk": {"B": wrapped},
                                    "created_at": {"N": "1700000000"},
                                }
                            }
                        ]
                    },
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
        assert body["currentVmkVersion"] == 1
        assert body["envelopeVersion"] == 1
        assert body["vmkEnvelopes"] == [
            {
                "vmkVersion": 1,
                "wrappedVmk": base64.b64encode(wrapped).decode("utf-8"),
                "createdAt": 1700000000,
            }
        ]
        # Nothing stored on this row: the optional name is null.
        assert body["encryptedName"] is None
        assert "verifier" not in body
        assert "kekVersion" not in body
        assert "pendingVaultSalt" not in body
        assert "pendingVerifier" not in body

    def test_get_vault_returns_vmk_envelopes(self, client, dynamodb_stubber):
        user_id = "test-user-id"
        vault_id = "test-vault-1"
        encrypted_name = secrets.token_bytes(40)
        wrapped1 = secrets.token_bytes(61)
        wrapped2 = secrets.token_bytes(61)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": vault_row(
                    user_id,
                    vault_id,
                    encrypted_name={"B": encrypted_name},
                    current_vmk_version={"N": "2"},
                    envelope_version={"N": "1"},
                    vmk_envelopes={
                        "L": [
                            {
                                "M": {
                                    "vmk_version": {"N": "1"},
                                    "wrapped_vmk": {"B": wrapped1},
                                    "created_at": {"N": "1700000000"},
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
                    updated_at={"N": "1700000500"},
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
        assert body["currentVmkVersion"] == 2
        assert body["envelopeVersion"] == 1
        envelopes = body["vmkEnvelopes"]
        assert [e["vmkVersion"] for e in envelopes] == [1, 2]
        assert base64.b64decode(envelopes[0]["wrappedVmk"]) == wrapped1
        assert base64.b64decode(envelopes[1]["wrappedVmk"]) == wrapped2


class TestUpdateVaultRotationRoute:
    """POST /v1/vaults/{vault_id}/rotation: ACQUIRE appends an envelope, RELEASE flips IDLE."""

    VAULT = "test-vault-1"
    KEY = {"PK": "USER#test-user-id", "SK": "VAULT#test-vault-1"}

    def _stub_consistent_read(self, dynamodb_stubber, **extra):
        dynamodb_stubber.add_response(
            "get_item",
            {"Item": vault_row("test-user-id", self.VAULT, **extra)},
            {"TableName": "test-vaults-table", "Key": self.KEY, "ConsistentRead": True},
        )

    def _acquire_body(self, **extra):
        body = {
            "action": "ACQUIRE",
            "expectedState": "IDLE",
            "expectedEnvelopeVersion": 1,
            "newVmkVersion": 2,
            "wrappedNewVmk": base64.b64encode(secrets.token_bytes(61)).decode("utf-8"),
        }
        body.update(extra)
        return body

    def test_acquire_appends_envelope_and_bumps(self, client, dynamodb_stubber):
        wrapped = secrets.token_bytes(61)
        self._stub_consistent_read(
            dynamodb_stubber,
            current_vmk_version={"N": "1"},
            envelope_version={"N": "1"},
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
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IN_PROGRESS"},
                    "rotation_locked_at": {"N": str(int(time.time()))},
                    "current_vmk_version": {"N": "2"},
                    "envelope_version": {"N": "2"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": self.KEY,
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = client.post(
            f"/v1/vaults/{self.VAULT}/rotation",
            json=self._acquire_body(wrappedNewVmk=base64.b64encode(wrapped).decode("utf-8")),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["rotationState"] == "IN_PROGRESS"
        assert body["currentVmkVersion"] == 2
        assert body["envelopeVersion"] == 2

    def test_acquire_wrong_next_version_returns_400(self, client, dynamodb_stubber):
        self._stub_consistent_read(
            dynamodb_stubber, current_vmk_version={"N": "2"}, envelope_version={"N": "1"}
        )

        response = client.post(f"/v1/vaults/{self.VAULT}/rotation", json=self._acquire_body())

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "BAD_REQUEST"

    def test_acquire_stale_envelope_returns_409(self, client, dynamodb_stubber):
        self._stub_consistent_read(
            dynamodb_stubber, current_vmk_version={"N": "1"}, envelope_version={"N": "1"}
        )
        dynamodb_stubber.add_client_error(
            "update_item", service_error_code="ConditionalCheckFailedException"
        )
        dynamodb_stubber.add_response(
            "get_item",
            {"Item": vault_row("test-user-id", self.VAULT)},
            {"TableName": "test-vaults-table", "Key": self.KEY},
        )

        response = client.post(
            f"/v1/vaults/{self.VAULT}/rotation", json=self._acquire_body(expectedEnvelopeVersion=0)
        )

        assert response.status_code == 409

    def test_acquire_unknown_vault_returns_404(self, client, dynamodb_stubber):
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {"TableName": "test-vaults-table", "Key": self.KEY, "ConsistentRead": True},
        )

        response = client.post(f"/v1/vaults/{self.VAULT}/rotation", json=self._acquire_body())

        assert response.status_code == 404

    def test_release_flips_idle_and_stores_name(self, client, dynamodb_stubber):
        new_name = secrets.token_bytes(40)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "rotation_state": {"S": "IDLE"},
                    "rotation_locked_at": {"N": "1700000500"},
                    "current_vmk_version": {"N": "2"},
                    "envelope_version": {"N": "2"},
                }
            },
            {
                "TableName": "test-vaults-table",
                "Key": self.KEY,
                "UpdateExpression": (
                    "SET rotation_state = :idle, updated_at = :now, encrypted_name = :name"
                ),
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = client.post(
            f"/v1/vaults/{self.VAULT}/rotation",
            json={
                "action": "RELEASE",
                "expectedState": "IN_PROGRESS",
                "newEncryptedName": base64.b64encode(new_name).decode("utf-8"),
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["rotationState"] == "IDLE"
        assert body["currentVmkVersion"] == 2
        assert body["envelopeVersion"] == 2

    def test_acquire_without_envelope_version_returns_400(self, client, dynamodb_stubber):
        # No DynamoDB stub: the request is rejected before any I/O.
        body = self._acquire_body()
        del body["expectedEnvelopeVersion"]

        response = client.post(f"/v1/vaults/{self.VAULT}/rotation", json=body)

        assert response.status_code == 400


class TestListVaultsRoute:
    """Test suite for ListVaultsRoute through FastAPI test client."""

    def test_list_vaults_returns_page_and_next_token(self, client, dynamodb_stubber):
        user_id = "test-user-id"
        salt_a = secrets.token_bytes(16)
        salt_b = secrets.token_bytes(16)
        name_a = secrets.token_bytes(40)
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
                        "created_at": {"N": "1700000000"},
                        "updated_at": {"N": "1700000900"},
                        "current_vmk_version": {"N": "2"},
                        "rotation_state": {"S": "IN_PROGRESS"},
                    },
                    {
                        "PK": {"S": f"USER#{user_id}"},
                        "SK": {"S": "VAULT#vault-b"},
                        "vault_id": {"S": "vault-b"},
                        "user_id": {"S": user_id},
                        "vault_salt": {"B": salt_b},
                        "created_at": {"N": "1700001000"},
                        "updated_at": {"N": "1700001000"},
                        "current_vmk_version": {"N": "1"},
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
        assert first["currentVmkVersion"] == 2
        assert first["rotationState"] == "IN_PROGRESS"
        assert first["createdAt"] == 1700000000
        assert first["updatedAt"] == 1700000900
        assert "verifier" not in first
        assert second["encryptedName"] is None
        assert second["currentVmkVersion"] == 1
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

    def test_update_vault_verifier_only_is_rejected(self, client):
        # `verifier` is gone from the contract: an unknown field is ignored, so the
        # route sees no encryptedName and rejects before touching DynamoDB.
        response = client.put(
            "/v1/vaults/test-vault-1",
            json={"verifier": base64.b64encode(secrets.token_bytes(48)).decode("utf-8")},
        )

        assert response.status_code == 400
        assert response.json()["error"]["message"] == "Provide encryptedName"

    def test_update_vault_empty_body_returns_400(self, client):
        # No stub: the route rejects before touching DynamoDB.
        response = client.put("/v1/vaults/test-vault-1", json={})

        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "BAD_REQUEST"
        assert body["error"]["message"] == "Provide encryptedName"

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
            json={"encryptedName": base64.b64encode(secrets.token_bytes(40)).decode("utf-8")},
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

    def test_idle_vault_after_vmk_rotation_is_deleted_in_one_call(self, client, dynamodb_stubber):
        stub_mark(dynamodb_stubber, self.USER, self.VAULT, rotation_state="IDLE")
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


class TestUpdateVaultPasswordRoute:
    """POST /v1/vaults/{vault_id}/password: bootstrap and pure re-wrap."""

    VAULT = "test-vault-1"

    def test_bootstrap_returns_1(self, client, dynamodb_stubber):
        wrapped = secrets.token_bytes(61)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": vault_row(
                    "test-user-id",
                    self.VAULT,
                    envelope_version={"N": "0"},
                    current_vmk_version={"N": "0"},
                )
            },
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{self.VAULT}"},
                "ConsistentRead": True,
            },
        )
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{self.VAULT}"},
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        response = client.post(
            f"/v1/vaults/{self.VAULT}/password",
            json={
                "expectedEnvelopeVersion": 0,
                "vmkEnvelopes": [
                    {
                        "vmkVersion": 1,
                        "wrappedVmk": base64.b64encode(wrapped).decode("utf-8"),
                        "createdAt": 1700000400,
                    }
                ],
            },
        )

        assert response.status_code == 200
        assert response.json() == {"envelopeVersion": 1}

    def test_unknown_vault_returns_404(self, client, dynamodb_stubber):
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-vaults-table",
                "Key": {"PK": "USER#test-user-id", "SK": f"VAULT#{self.VAULT}"},
                "ConsistentRead": True,
            },
        )

        response = client.post(
            f"/v1/vaults/{self.VAULT}/password",
            json={
                "expectedEnvelopeVersion": 0,
                "vmkEnvelopes": [
                    {
                        "vmkVersion": 1,
                        "wrappedVmk": base64.b64encode(secrets.token_bytes(61)).decode("utf-8"),
                        "createdAt": 1700000400,
                    }
                ],
            },
        )

        assert response.status_code == 404
