"""
Unit tests for item route handlers.

Tests verify that item routes work correctly through the FastAPI test client.
"""

import base64
from datetime import datetime, timezone

from botocore.stub import ANY


class TestCreateItemRoute:
    """Test suite for CreateItemRoute through FastAPI test client."""

    def test_create_item_route_handler(self, client, dynamodb_stubber):
        """Test create item route handler returns expected response."""
        vault_id = "test-vault-456"

        # Stub DynamoDB put_item call
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = client.post(
            "/v1/items",
            json={
                "vaultId": vault_id,
                "itemType": "NOTE",
                "encryptedContent": "ZW5jcnlwdGVkLWNvbnRlbnQ=",
                "encryptedMetadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
            },
        )

        assert response.status_code == 200
        body = response.json()

        assert "itemId" in body, "Response should include itemId"
        assert "itemType" in body, "Response should include itemType"
        assert "createdAt" in body, "Response should include createdAt"

        assert isinstance(body["itemId"], str), "itemId should be a string"
        assert len(body["itemId"]) > 0, "itemId should not be empty"
        assert body["itemType"] == "NOTE", f"itemType should be NOTE, got {body['itemType']}"

        # createdAt is an epoch timestamp (number), not an ISO string
        assert isinstance(body["createdAt"], (int, float))


class TestInitiateUploadRoute:
    """Test suite for InitiateUploadRoute through FastAPI test client."""

    def test_initiate_upload_route_handler(self, client, dynamodb_stubber):
        """Test initiate upload route handler returns expected response."""
        vault_id = "test-vault-456"

        # Stub DynamoDB put_item call (creates item metadata)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": "test-items-table",
                "Item": ANY,
            },
        )

        response = client.post(
            "/v1/items/upload/init",
            json={
                "vaultId": vault_id,
                "encryptedMetadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                "sizeBytes": 50 * 1024 * 1024,  # 50MB - small file
            },
        )

        assert response.status_code == 200
        body = response.json()

        assert "itemId" in body, "Response should include itemId"
        assert "uploadUrl" in body, "Response should include uploadUrl"
        assert "expiresAt" in body, "Response should include expiresAt"
        assert "s3Key" in body, "Response should include s3Key"

        assert isinstance(body["itemId"], str), "itemId should be a string"
        assert len(body["itemId"]) > 0, "itemId should not be empty"

        assert isinstance(body["uploadUrl"], str), "uploadUrl should be a string"
        assert body["uploadUrl"].startswith("https://"), "uploadUrl should be HTTPS"

        assert isinstance(body["s3Key"], str), "s3Key should be a string"
        assert vault_id in body["s3Key"], f"s3Key should contain vault_id {vault_id}"
        assert body["itemId"] in body["s3Key"], "s3Key should contain itemId"

        # expiresAt is an epoch timestamp (number), not an ISO string
        assert isinstance(body["expiresAt"], (int, float))


class TestCompleteUploadRoute:
    """Test suite for CompleteUploadRoute through FastAPI test client."""

    def test_complete_upload_route_handler(
        self, client, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test complete upload route handler returns expected response."""
        user_id = "test-user-id"
        vault_id = "test-vault-456"
        item_id = "test-item-789"
        s3_key = f"vaults/{vault_id}/files/{item_id}/test"

        # Stub DynamoDB get_item call (retrieve item metadata)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": vault_id},
                    "s3_key": {"S": s3_key},
                    "upload_status": {"S": "PENDING"},
                }
            },
            expected_params={
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"ITEM#{item_id}",
                },
            },
        )

        # Stub S3 head_object call (verify file exists)
        s3_stubber.add_response(
            "head_object",
            {
                "ContentLength": 1000,
                "ContentType": "image/jpeg",
            },
            {
                "Bucket": files_bucket_name,
                "Key": s3_key,
            },
        )

        # Stub DynamoDB update_item call (mark upload complete)
        now_timestamp = int(datetime.now(tz=timezone.utc).timestamp())
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "upload_status": {"S": "COMPLETE"},
                    "updated_at": {"N": str(now_timestamp)},
                }
            },
            {
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"ITEM#{item_id}",
                },
                "UpdateExpression": ANY,
                "ConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        # itemId is in the path now (Smithy contract); no request body.
        response = client.post(f"/v1/items/{item_id}/upload/complete")

        assert response.status_code == 200
        body = response.json()

        assert "itemId" in body, "Response should include itemId"
        assert "completedAt" in body, "Response should include completedAt"

        assert body["itemId"] == item_id, f"itemId should be {item_id}, got {body['itemId']}"

        # completedAt is an epoch timestamp; should be within ~60s of now
        now_ts = datetime.now(tz=timezone.utc).timestamp()
        assert (
            abs(now_ts - body["completedAt"]) < 60
        ), f"completedAt not recent: {body['completedAt']}"


class TestListItemsRoute:
    """Test suite for ListItemsRoute through FastAPI test client."""

    def test_list_items_route_handler_missing_vault_id(self, client):
        """Test list items route handler returns error when vault_id is missing."""
        response = client.get("/v1/items")

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422

    def test_list_items_route_handler_with_vault_id(
        self, client, dynamodb_stubber, vaults_table_name, items_table_name
    ):
        """Test list items route handler with vault_id returns empty list for empty vault."""
        user_id = "test-user-id"
        vault_id = "vault-123"

        # Stub DynamoDB get_item call for vault_exists check
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                }
            },
            expected_params={
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        # Stub DynamoDB query call for list_items - empty vault
        dynamodb_stubber.add_response(
            "query",
            {"Items": []},
            expected_params={
                "TableName": items_table_name,
                "IndexName": "GSI2",
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "FilterExpression": ANY,
                "ScanIndexForward": ANY,
                "Limit": ANY,
            },
        )

        response = client.get("/v1/items", params={"vaultId": vault_id})
        body = response.json()

        assert response.status_code == 200
        assert body["items"] == []

    def test_list_items_returns_404_for_nonexistent_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        """Test that list items returns 404 when vault doesn't exist."""
        user_id = "test-user-id"
        vault_id = "nonexistent-vault"

        # Stub DynamoDB get_item call for vault_exists - vault not found
        dynamodb_stubber.add_response(
            "get_item",
            {},
            expected_params={
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.get("/v1/items", params={"vaultId": vault_id})

        assert response.status_code == 404
        body = response.json()
        assert "Vault not found" in body["error"]["message"]

    def test_list_items_returns_404_for_vault_owned_by_different_user(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        """Test that list items returns 404 when vault exists but belongs to different user."""
        user_id = "test-user-id"
        vault_id = "vault-owned-by-other-user"

        # Stub DynamoDB get_item call for vault_exists - vault not found for THIS user
        dynamodb_stubber.add_response(
            "get_item",
            {},
            expected_params={
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.get("/v1/items", params={"vaultId": vault_id})

        assert response.status_code == 404
        body = response.json()
        assert "Vault not found" in body["error"]["message"]


class TestGetItemRoute:
    """Test suite for GetItemRoute through FastAPI test client."""

    def test_get_item_route_handler(self, client, dynamodb_stubber, items_table_name):
        """Test get item route handler with vault_id."""
        user_id = "test-user-id"
        vault_id = "vault-123"
        item_id = "test-item-123"

        now_timestamp = str(datetime.now(tz=timezone.utc).timestamp())
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "user_id": {"S": user_id},
                    "item_id": {"S": item_id},
                    "item_type": {"S": "EVENT"},
                    "vault_id": {"S": vault_id},
                    "encrypted_content": {"B": b"secret-content"},
                    "encrypted_metadata": {"B": b"foobar"},
                    "version": {"N": "1"},
                    "created_at": {"N": now_timestamp},
                    "updated_at": {"N": now_timestamp},
                }
            },
            expected_params={
                "Key": {"PK": "ITEM#test-item-123"},
                "TableName": items_table_name,
            },
        )

        response = client.get(f"/v1/items/{item_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["itemId"] == item_id
        assert body["itemType"] == "EVENT"
        assert body["vaultId"] == vault_id
        # blobs are base64 on the wire now (not raw UTF-8)
        assert body["encryptedMetadata"] == base64.b64encode(b"foobar").decode()
        assert "createdAt" in body
        assert "updatedAt" in body


class TestUpdateItemRoute:
    """Test suite for UpdateItemRoute through FastAPI test client."""

    def test_update_item_route_handler(self, client, dynamodb_stubber):
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "ITEM#item-1"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": "item-1"},
                    "item_type": {"S": "MEDIA"},
                    "vault_id": {"S": "vault-1"},
                    "user_id": {"S": "test-user-id"},
                    "encrypted_metadata": {"B": b"old"},
                    "encrypted_tags": {"L": [{"B": b"tagA"}]},
                    "created_at": {"N": "1"},
                    "updated_at": {"N": "1"},
                    "version": {"N": "1"},
                }
            },
            {"TableName": "test-items-table", "Key": ANY},
        )
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {}},
            {
                "TableName": "test-items-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )
        dynamodb_stubber.add_response(
            "batch_write_item", {"UnprocessedItems": {}}, {"RequestItems": ANY}
        )

        response = client.put(
            "/v1/items/item-1",
            json={
                "encryptedMetadata": "bmV3LW1ldGE=",
                "encryptedTags": ["dGFnQg=="],
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["itemId"] == "item-1"
        assert body["version"] == 2


class TestDeleteItemRoute:
    """Test suite for DeleteItemRoute through FastAPI test client."""

    def test_delete_item_route_handler(self, client, dynamodb_stubber, items_table_name):
        """Test delete item route handler successfully deletes an item."""
        user_id = "test-user-id"
        item_id = "test-item-123"
        vault_id = "test-vault-456"

        # Stub DynamoDB get_item call (retrieve item to verify ownership)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": vault_id},
                    "item_type": {"S": "NOTE"},
                    "encrypted_metadata": {"B": b"test-metadata"},
                }
            },
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        # Stub DynamoDB delete_item call
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        response = client.delete(f"/v1/items/{item_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Item deleted successfully"
        assert "deletedAt" in body

    def test_delete_item_route_enforces_user_authorization(
        self, client, dynamodb_stubber, items_table_name
    ):
        """Test that delete item route enforces user ownership authorization."""
        different_user_id = "different-user-456"
        item_id = "test-item-123"
        vault_id = "test-vault-456"

        # Stub DynamoDB get_item call - returns item owned by different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": different_user_id},
                    "vault_id": {"S": vault_id},
                    "item_type": {"S": "NOTE"},
                    "encrypted_metadata": {"B": b"test-metadata"},
                }
            },
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        response = client.delete(f"/v1/items/{item_id}")

        assert response.status_code == 404

    def test_delete_item_route_returns_404_for_nonexistent_item(
        self, client, dynamodb_stubber, items_table_name
    ):
        """Test delete item route returns 404 when item doesn't exist."""
        item_id = "nonexistent-item"

        # Stub DynamoDB get_item call - returns empty (no item found)
        dynamodb_stubber.add_response(
            "get_item",
            {},
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        response = client.delete(f"/v1/items/{item_id}")

        assert response.status_code == 404


class TestDownloadItemRoute:
    """Test suite for DownloadItemRoute through FastAPI test client."""

    def test_download_item_route_handler(
        self, client, dynamodb_stubber, s3_stubber, files_bucket_name
    ):
        """Test download item route handler with vault_id."""
        user_id = "test-user-id"
        item_id = "test-item-123"
        vault_id = "vault-123"
        s3_key = f"vaults/{vault_id}/files/{item_id}/test"

        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": f"VAULT#{vault_id}"},
                    "s3_key": {"S": s3_key},
                    "item_type": {"S": "MEDIA"},
                    "upload_status": {"S": "COMPLETED"},
                    "encrypted_metadata": {"B": "foobar".encode()},
                }
            },
            expected_params={
                "TableName": "test-items-table",
                "Key": {
                    "PK": f"ITEM#{item_id}",
                },
            },
        )

        s3_stubber.add_response(
            "head_object", {}, expected_params={"Bucket": files_bucket_name, "Key": s3_key}
        )

        response = client.get(f"/v1/items/{item_id}/download")
        body = response.json()

        assert response.status_code == 200
        assert "downloadUrl" in body
        assert s3_key in body["downloadUrl"]
        assert "expiresAt" in body


class TestSearchItemRoute:
    """Test suite for SearchItemsRoute through FastAPI test client."""

    def test_search_items_route_handler(self, client):
        """Test search items route handler returns expected response."""
        response = client.post("/v1/items/search")

        assert response.status_code == 200
        body = response.json()
        assert "Search items endpoint" in body["message"]
