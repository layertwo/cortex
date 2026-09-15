"""
Wire-form rows and Stubber helpers shared by the vault deletion tests.

Expected params are in boto3 resource (Python) form because the Stubber
checks them before the DynamoDB type transformation; responses are in wire
form because they pass through the deserializer. Expression strings are
pinned to the spec literals (docs/plans/2026-09-14-multivault-backend-design.md
sections 4.3 and 5) because the Stubber never evaluates them.
"""

import base64

from botocore.stub import ANY

VAULTS_TABLE = "test-vaults-table"
ITEMS_TABLE = "test-items-table"
COLLECTIONS_TABLE = "test-collections-table"
SHARES_TABLE = "test-shares-table"
BUCKET = "test-files-bucket"

MARK_UPDATE_EXPRESSION = (
    "SET deletion_state = :deleting, deletion_started_at = :now, updated_at = :now"
)
MARK_CONDITION_EXPRESSION = (
    "attribute_exists(PK) AND attribute_not_exists(deletion_state) AND "
    "(attribute_not_exists(rotation_state) OR rotation_state IN (:idle, :paused) OR "
    "(rotation_state = :in_progress AND rotation_locked_at < :stale))"
)
ROW_DELETE_CONDITION = "deletion_state = :deleting"
ITEMS_KEY_CONDITION = "GSI2PK = :pk"
COLLECTIONS_KEY_CONDITION = "PK = :pk AND begins_with(SK, :sk_prefix)"
MEMBERSHIPS_KEY_CONDITION = "PK = :pk"
SHARES_FILTER = "vault_id = :v AND user_id = :u"


# --- keys (Python form) -----------------------------------------------------


def vault_key(user_id: str, vault_id: str) -> dict:
    return {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}


def item_key(item_id: str) -> dict:
    return {"PK": f"ITEM#{item_id}", "SK": "METADATA"}


def tag_key(vault_id: str, item_id: str, tag: bytes) -> dict:
    tag_b64 = base64.b64encode(tag).decode("utf-8")
    return {"PK": f"VAULT#{vault_id}#TAG#{tag_b64}", "SK": f"ITEM#{item_id}"}


def collection_key(vault_id: str, collection_id: str) -> dict:
    return {"PK": f"VAULT#{vault_id}", "SK": f"COLLECTION#{collection_id}"}


def membership_key(collection_id: str, item_id: str) -> dict:
    return {"PK": f"COLLECTION#{collection_id}", "SK": f"ITEM#{item_id}"}


def share_key(share_id: str) -> dict:
    return {"PK": f"SHARE#{share_id}", "SK": "METADATA"}


def s3_key_for(vault_id: str, item_id: str) -> str:
    return f"vaults/{vault_id}/files/{item_id}/blob"


def wire(key: dict) -> dict:
    """String-only Python-form key -> DynamoDB wire form (for LastEvaluatedKey)."""
    return {name: {"S": value} for name, value in key.items()}


# --- rows (wire form, as returned by query/scan) -----------------------------


def media_row(
    item_id: str,
    vault_id: str,
    user_id: str,
    upload_status: str = "COMPLETE",
    upload_id: str | None = None,
    tags: tuple[bytes, ...] = (),
) -> dict:
    row = {
        "PK": {"S": f"ITEM#{item_id}"},
        "SK": {"S": "METADATA"},
        "item_id": {"S": item_id},
        "item_type": {"S": "MEDIA"},
        "vault_id": {"S": vault_id},
        "user_id": {"S": user_id},
        "s3_key": {"S": s3_key_for(vault_id, item_id)},
        "upload_status": {"S": upload_status},
        "encrypted_metadata": {"B": b"opaque"},
        "GSI2PK": {"S": f"VAULT#{vault_id}"},
        "GSI2SK": {"S": f"ITEM#{item_id}"},
    }
    if upload_id:
        row["upload_id"] = {"S": upload_id}
    if tags:
        row["encrypted_tags"] = {"L": [{"B": tag} for tag in tags]}
    return row


def note_row(item_id: str, vault_id: str, user_id: str, tags: tuple[bytes, ...] = ()) -> dict:
    row = {
        "PK": {"S": f"ITEM#{item_id}"},
        "SK": {"S": "METADATA"},
        "item_id": {"S": item_id},
        "item_type": {"S": "NOTE"},
        "vault_id": {"S": vault_id},
        "user_id": {"S": user_id},
        "encrypted_content": {"B": b"opaque"},
        "encrypted_metadata": {"B": b"opaque"},
        "GSI2PK": {"S": f"VAULT#{vault_id}"},
        "GSI2SK": {"S": f"ITEM#{item_id}"},
    }
    if tags:
        row["encrypted_tags"] = {"L": [{"B": tag} for tag in tags]}
    return row


def collection_row(collection_id: str, vault_id: str, user_id: str, **extra: dict) -> dict:
    return {
        "PK": {"S": f"VAULT#{vault_id}"},
        "SK": {"S": f"COLLECTION#{collection_id}"},
        "collection_id": {"S": collection_id},
        "vault_id": {"S": vault_id},
        "user_id": {"S": user_id},
        "encrypted_metadata": {"B": b"opaque"},
        "created_at": {"N": "1234567890"},
        "updated_at": {"N": "1234567890"},
        "item_count": {"N": "0"},
        **extra,
    }


def membership_row(collection_id: str, item_id: str, vault_id: str, user_id: str) -> dict:
    return {
        "PK": {"S": f"COLLECTION#{collection_id}"},
        "SK": {"S": f"ITEM#{item_id}"},
        "collection_id": {"S": collection_id},
        "item_id": {"S": item_id},
        "vault_id": {"S": vault_id},
        "user_id": {"S": user_id},
    }


def share_row(share_id: str, vault_id: str, user_id: str) -> dict:
    return {
        "PK": {"S": f"SHARE#{share_id}"},
        "SK": {"S": "METADATA"},
        "share_id": {"S": share_id},
        "item_id": {"S": "item-shared"},
        "vault_id": {"S": vault_id},
        "user_id": {"S": user_id},
        "is_revoked": {"BOOL": False},
    }


def vault_row(user_id: str, vault_id: str, **attrs: dict) -> dict:
    row = {
        "PK": {"S": f"USER#{user_id}"},
        "SK": {"S": f"VAULT#{vault_id}"},
        "vault_id": {"S": vault_id},
        "user_id": {"S": user_id},
        "vault_salt": {"B": b"\xaa" * 16},
        "created_at": {"N": "1700000000"},
    }
    row.update(attrs)
    return row


# --- stubs, in the order the service issues the calls ------------------------


def stub_mark(stubber, user_id: str, vault_id: str, rotation_state: str = "IDLE") -> None:
    """Step 0 success: the conditional update that writes deletion_state."""
    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "deletion_state": {"S": "DELETING"},
                "rotation_state": {"S": rotation_state},
            }
        },
        {
            "TableName": VAULTS_TABLE,
            "Key": vault_key(user_id, vault_id),
            "UpdateExpression": MARK_UPDATE_EXPRESSION,
            "ConditionExpression": MARK_CONDITION_EXPRESSION,
            "ExpressionAttributeValues": ANY,
        },
    )


def stub_vault_lookup(stubber, user_id: str, vault_id: str, row: dict | None = None) -> None:
    """vault_exists -> get_item on the caller's vault row; row=None is a miss."""
    stubber.add_response(
        "get_item",
        {"Item": row} if row else {},
        {"TableName": VAULTS_TABLE, "Key": vault_key(user_id, vault_id)},
    )


def stub_mark_condition_failed(stubber, user_id: str, vault_id: str, item: dict | None) -> None:
    """Step 0 conditional failure followed by the disambiguating get_item."""
    stubber.add_client_error(
        "update_item",
        service_error_code="ConditionalCheckFailedException",
        expected_params={
            "TableName": VAULTS_TABLE,
            "Key": vault_key(user_id, vault_id),
            "UpdateExpression": MARK_UPDATE_EXPRESSION,
            "ConditionExpression": MARK_CONDITION_EXPRESSION,
            "ExpressionAttributeValues": ANY,
        },
    )
    stubber.add_response(
        "get_item",
        {"Item": item} if item else {},
        {"TableName": VAULTS_TABLE, "Key": vault_key(user_id, vault_id)},
    )


def _stub_page(
    stubber, op: str, expected: dict, rows: list, last_key: dict | None, start_key: dict | None
) -> None:
    """One page. last_key is wire form (response); start_key is Python form (expected)."""
    if start_key:
        expected["ExclusiveStartKey"] = start_key
    response: dict = {"Items": rows}
    if last_key:
        response["LastEvaluatedKey"] = last_key
    stubber.add_response(op, response, expected)


def stub_items_page(
    stubber, vault_id: str, rows: list, last_key: dict | None = None, start_key: dict | None = None
) -> None:
    """Step 1: one GSI2 page."""
    expected = {
        "TableName": ITEMS_TABLE,
        "IndexName": "GSI2",
        "KeyConditionExpression": ITEMS_KEY_CONDITION,
        "ExpressionAttributeValues": {":pk": f"VAULT#{vault_id}"},
        "Limit": 25,
        "ScanIndexForward": True,
    }
    _stub_page(stubber, "query", expected, rows, last_key, start_key)


def stub_collections_page(
    stubber, vault_id: str, rows: list, last_key: dict | None = None, start_key: dict | None = None
) -> None:
    """Step 2: one page of collection rows on the collections table."""
    expected = {
        "TableName": COLLECTIONS_TABLE,
        "KeyConditionExpression": COLLECTIONS_KEY_CONDITION,
        "ExpressionAttributeValues": {":pk": f"VAULT#{vault_id}", ":sk_prefix": "COLLECTION#"},
        "Limit": 25,
        "ScanIndexForward": True,
    }
    _stub_page(stubber, "query", expected, rows, last_key, start_key)


def stub_shares_page(
    stubber,
    user_id: str,
    vault_id: str,
    rows: list,
    last_key: dict | None = None,
    start_key: dict | None = None,
) -> None:
    """Step 3: one filtered scan page on the shares table."""
    expected = {
        "TableName": SHARES_TABLE,
        "FilterExpression": SHARES_FILTER,
        "ExpressionAttributeValues": {":v": vault_id, ":u": user_id},
        "Limit": 100,
    }
    _stub_page(stubber, "scan", expected, rows, last_key, start_key)


def stub_batch_delete(stubber, table: str, keys: list) -> None:
    """One batch_writer flush: at most 25 DeleteRequests, in insertion order."""
    assert 0 < len(keys) <= 25, "batch_writer flushes at most 25 requests"
    stubber.add_response(
        "batch_write_item",
        {"UnprocessedItems": {}},
        {"RequestItems": {table: [{"DeleteRequest": {"Key": key}} for key in keys]}},
    )


def stub_purge(stubber, vault_id: str, collection_id: str, item_ids: list, user_id: str) -> None:
    """purge_collection: membership query (limit 100), batch deletes, collection row delete."""
    stubber.add_response(
        "query",
        {"Items": [membership_row(collection_id, i, vault_id, user_id) for i in item_ids]},
        {
            "TableName": COLLECTIONS_TABLE,
            "KeyConditionExpression": MEMBERSHIPS_KEY_CONDITION,
            "ExpressionAttributeValues": {":pk": f"COLLECTION#{collection_id}"},
            "Limit": 100,
            "ScanIndexForward": True,
        },
    )
    keys = [membership_key(collection_id, i) for i in item_ids]
    for start in range(0, len(keys), 25):
        stub_batch_delete(stubber, COLLECTIONS_TABLE, keys[start : start + 25])
    stubber.add_response(
        "delete_item",
        {},
        {"TableName": COLLECTIONS_TABLE, "Key": collection_key(vault_id, collection_id)},
    )


def stub_s3_delete(s3_stubber, s3_key: str) -> None:
    s3_stubber.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": s3_key})


def stub_s3_abort(s3_stubber, s3_key: str, upload_id: str) -> None:
    s3_stubber.add_response(
        "abort_multipart_upload", {}, {"Bucket": BUCKET, "Key": s3_key, "UploadId": upload_id}
    )


def stub_row_delete(stubber, user_id: str, vault_id: str) -> None:
    """Step 4: the conditional delete of the vault row."""
    stubber.add_response(
        "delete_item",
        {},
        {
            "TableName": VAULTS_TABLE,
            "Key": vault_key(user_id, vault_id),
            "ConditionExpression": ROW_DELETE_CONDITION,
            "ExpressionAttributeValues": {":deleting": "DELETING"},
        },
    )


def stub_empty_tail(stubber, user_id: str, vault_id: str, from_step: int = 1) -> None:
    """Terminating pages: empty items (step 1), empty collections (2), empty scan (3)."""
    if from_step <= 1:
        stub_items_page(stubber, vault_id, [])
    if from_step <= 2:
        stub_collections_page(stubber, vault_id, [])
    stub_shares_page(stubber, user_id, vault_id, [])
