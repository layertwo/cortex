"""
Unit tests for RotationAbandonService (spec section 3): the re-keyed-row
safety check that gates ABANDON.

Each test pins the exact Stubber sequence: get_item (vault) -> query GSI2
items -> query collections -> the conditional update_item (abandon_rotation).
A page holding a re-keyed row raises before any further call, so a passing
test also proves no extra work happened.
"""

import time

import pytest
from botocore.stub import ANY

from src.api.services.vault_service import STALE_LOCK_SECONDS
from src.shared.exceptions import ConflictError
from tests.fixtures.vault_deletion import vault_row, wire

USER = "user-a"
VAULT = "vault-a"

ROTATION_LOCKED_AT = 1699999000
ROTATION_GENERATION = 4
STALE_LOCK = int(time.time()) - STALE_LOCK_SECONDS - 100
CONFLICT_MESSAGE = "A vault password change is already in progress on another device"

VAULTS_TABLE = "test-vaults-table"
ITEMS_TABLE = "test-items-table"
COLLECTIONS_TABLE = "test-collections-table"

REKEYED_MESSAGE = (
    "Some files were already re-keyed; finish the password change with the new password"
)

ABANDON_UPDATE = (
    "SET rotation_state = :idle, updated_at = :now"
    " REMOVE pending_vault_salt, pending_verifier, rotation_locked_at"
)
ABANDON_CONDITION = (
    "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND ("
    "rotation_state = :paused OR "
    "(rotation_state = :in_progress AND rotation_locked_at < :stale))"
)


def _vault_key(user_id: str, vault_id: str) -> dict:
    return {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}


def _item_row(vault_id: str, item_id: str, dek_version: int) -> dict:
    return {
        "PK": {"S": f"ITEM#{item_id}"},
        "SK": {"S": "METADATA"},
        "item_id": {"S": item_id},
        "vault_id": {"S": vault_id},
        "dek_version": {"N": str(dek_version)},
        "GSI2PK": {"S": f"VAULT#{vault_id}"},
    }


def _collection_row(vault_id: str, collection_id: str, metadata_version: int) -> dict:
    return {
        "PK": {"S": f"VAULT#{vault_id}"},
        "SK": {"S": f"COLLECTION#{collection_id}"},
        "collection_id": {"S": collection_id},
        "vault_id": {"S": vault_id},
        "metadata_version": {"N": str(metadata_version)},
    }


def _stub_vault(
    stubber,
    kek_version: int = 1,
    rotation_locked_at: int = ROTATION_LOCKED_AT,
) -> None:
    """get_item for the vault: PAUSED with a staged pair, at the given kek_version."""
    row = vault_row(
        USER,
        VAULT,
        rotation_state={"S": "PAUSED"},
        pending_vault_salt={"B": b"\x01" * 16},
        pending_verifier={"B": b"\x02" * 32},
        kek_version={"N": str(kek_version)},
        rotation_locked_at={"N": str(rotation_locked_at)},
        rotation_generation={"N": str(ROTATION_GENERATION)},
    )
    stubber.add_response(
        "get_item", {"Item": row}, {"TableName": VAULTS_TABLE, "Key": _vault_key(USER, VAULT)}
    )


def _stub_vault_state(
    stubber,
    rotation_state: str,
    rotation_locked_at: int | None = None,
    kek_version: int = 1,
) -> None:
    """get_item for the vault in an arbitrary rotation_state, for the pre-flight check tests."""
    attrs = {"rotation_state": {"S": rotation_state}, "kek_version": {"N": str(kek_version)}}
    if rotation_locked_at is not None:
        attrs["rotation_locked_at"] = {"N": str(rotation_locked_at)}
    row = vault_row(USER, VAULT, **attrs)
    stubber.add_response(
        "get_item", {"Item": row}, {"TableName": VAULTS_TABLE, "Key": _vault_key(USER, VAULT)}
    )


def _stub_items_page(
    stubber, rows: list, kek_version: int = 1, last_key: dict | None = None, start_key=None
) -> None:
    expected = {
        "TableName": ITEMS_TABLE,
        "IndexName": "GSI2",
        "KeyConditionExpression": "GSI2PK = :pk",
        "FilterExpression": "dek_version > :kek",
        "ExpressionAttributeValues": {":pk": f"VAULT#{VAULT}", ":kek": kek_version},
        "Limit": 100,
        "ScanIndexForward": True,
    }
    if start_key:
        expected["ExclusiveStartKey"] = start_key
    response = {"Items": rows}
    if last_key:
        response["LastEvaluatedKey"] = last_key
    stubber.add_response("query", response, expected)


def _stub_collections_page(
    stubber, rows: list, kek_version: int = 1, last_key: dict | None = None, start_key=None
) -> None:
    expected = {
        "TableName": COLLECTIONS_TABLE,
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :sk_prefix)",
        "FilterExpression": "metadata_version > :kek",
        "ExpressionAttributeValues": {
            ":pk": f"VAULT#{VAULT}",
            ":sk_prefix": "COLLECTION#",
            ":kek": kek_version,
        },
        "Limit": 100,
        "ScanIndexForward": True,
    }
    if start_key:
        expected["ExclusiveStartKey"] = start_key
    response = {"Items": rows}
    if last_key:
        response["LastEvaluatedKey"] = last_key
    stubber.add_response("query", response, expected)


def _stub_abandon_write(
    stubber,
    generation: int = ROTATION_GENERATION,
    locked_at: int | None = ROTATION_LOCKED_AT,
) -> None:
    if generation > 0:
        condition_suffix = " AND rotation_generation = :gen"
        extra_values = {":gen": generation}
    else:
        condition_suffix = " AND attribute_not_exists(rotation_generation)"
        extra_values = {}
    if locked_at is not None:
        condition_suffix += " AND rotation_locked_at = :seen"
        extra_values[":seen"] = locked_at
    stubber.add_response(
        "update_item",
        {"Attributes": {"rotation_state": {"S": "IDLE"}}},
        {
            "TableName": VAULTS_TABLE,
            "Key": _vault_key(USER, VAULT),
            "UpdateExpression": ABANDON_UPDATE,
            "ConditionExpression": ABANDON_CONDITION + condition_suffix,
            "ExpressionAttributeValues": {
                ":idle": "IDLE",
                ":now": ANY,
                ":paused": "PAUSED",
                ":in_progress": "IN_PROGRESS",
                ":stale": ANY,
                **extra_values,
            },
            "ReturnValues": "ALL_NEW",
        },
    )


class TestRotationAbandonService:
    def test_success_choreography_pins_the_write(self, rotation_abandon_service, dynamodb_stubber):
        """get_item -> empty items page -> empty collections page -> the ABANDON write."""
        _stub_vault(dynamodb_stubber)
        _stub_items_page(dynamodb_stubber, [])
        _stub_collections_page(dynamodb_stubber, [])
        _stub_abandon_write(dynamodb_stubber)

        result = rotation_abandon_service.abandon(USER, VAULT)

        assert result["rotation_state"] == "IDLE"

    def test_item_above_kek_raises_conflict_with_no_further_calls(
        self, rotation_abandon_service, dynamodb_stubber
    ):
        _stub_vault(dynamodb_stubber)
        _stub_items_page(dynamodb_stubber, [_item_row(VAULT, "i1", 2)])
        # No collections query and no update_item are stubbed: either would be
        # an unstubbed call and fail the test.

        with pytest.raises(ConflictError, match=REKEYED_MESSAGE):
            rotation_abandon_service.abandon(USER, VAULT)

    def test_collection_above_kek_raises_conflict(self, rotation_abandon_service, dynamodb_stubber):
        _stub_vault(dynamodb_stubber)
        _stub_items_page(dynamodb_stubber, [])
        _stub_collections_page(dynamodb_stubber, [_collection_row(VAULT, "c1", 2)])
        # No update_item is stubbed.

        with pytest.raises(ConflictError, match=REKEYED_MESSAGE):
            rotation_abandon_service.abandon(USER, VAULT)

    def test_item_check_follows_last_evaluated_key_across_two_pages(
        self, rotation_abandon_service, dynamodb_stubber
    ):
        cursor = {"PK": "ITEM#i1", "SK": "METADATA"}
        _stub_vault(dynamodb_stubber)
        _stub_items_page(dynamodb_stubber, [], last_key=wire(cursor))
        _stub_items_page(dynamodb_stubber, [], start_key=cursor)
        _stub_collections_page(dynamodb_stubber, [])
        _stub_abandon_write(dynamodb_stubber)

        result = rotation_abandon_service.abandon(USER, VAULT)

        assert result["rotation_state"] == "IDLE"

    def test_abandon_on_idle_vault_is_conflict_with_no_further_calls(
        self, rotation_abandon_service, dynamodb_stubber
    ):
        """The pre-flight check rejects an IDLE vault before any scan or write."""
        _stub_vault_state(dynamodb_stubber, "IDLE")

        with pytest.raises(ConflictError, match=CONFLICT_MESSAGE):
            rotation_abandon_service.abandon(USER, VAULT)

    def test_abandon_on_live_in_progress_vault_is_conflict_with_no_further_calls(
        self, rotation_abandon_service, dynamodb_stubber
    ):
        """A live (non-stale) IN_PROGRESS lock also fails the pre-flight check."""
        _stub_vault_state(dynamodb_stubber, "IN_PROGRESS", rotation_locked_at=int(time.time()))

        with pytest.raises(ConflictError, match=CONFLICT_MESSAGE):
            rotation_abandon_service.abandon(USER, VAULT)

    @pytest.mark.parametrize(
        "state, locked_at",
        [("IN_PROGRESS", STALE_LOCK), ("PAUSED", None)],
        ids=["stale_in_progress", "legacy_paused_no_lock"],
    )
    def test_preflight_admits_stale_lock_and_legacy_row(
        self, rotation_abandon_service, dynamodb_stubber, state, locked_at
    ):
        """Both reach the scans; neither row has a rotation_generation attribute, so the write pins absence."""
        _stub_vault_state(dynamodb_stubber, state, rotation_locked_at=locked_at)
        _stub_items_page(dynamodb_stubber, [])
        _stub_collections_page(dynamodb_stubber, [])
        _stub_abandon_write(dynamodb_stubber, generation=0, locked_at=locked_at)

        result = rotation_abandon_service.abandon(USER, VAULT)

        assert result["rotation_state"] == "IDLE"

    def test_rows_of_another_vault_are_ignored(self, rotation_abandon_service, dynamodb_stubber):
        """Per-row vault_id guard, same as the deletion sweep: foreign rows never block."""
        _stub_vault(dynamodb_stubber)
        _stub_items_page(dynamodb_stubber, [_item_row("vault-b", "i1", 2)])
        _stub_collections_page(dynamodb_stubber, [_collection_row("vault-b", "c1", 2)])
        _stub_abandon_write(dynamodb_stubber)

        result = rotation_abandon_service.abandon(USER, VAULT)

        assert result["rotation_state"] == "IDLE"
