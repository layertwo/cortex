"""
Unit tests for share route handlers.

Tests verify that share routes work correctly through the FastAPI test client.
"""

import time

from botocore.stub import ANY
from fastapi.testclient import TestClient

from src.environment.service_provider import ServiceProvider


class TestCreateShareRoute:
    """Test suite for CreateShareRoute through FastAPI test client."""

    def test_create_share_route_handler(
        self, client, dynamodb_stubber, items_table_name, shares_table_name
    ):
        """Test create share route handler returns expected response."""
        user_id = "test-user-id"
        item_id = "test-item-789"
        vault_id = "test-vault-456"

        # Stub 1: get_item on items table (verify user owns the item)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": vault_id},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/{vault_id}/files/{item_id}/test"},
                }
            },
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        # Stub 2: put_item on shares table (store share metadata)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": shares_table_name,
                "Item": ANY,
            },
        )

        response = client.post(
            "/v1/shares",
            json={"item_id": item_id},
        )

        assert response.status_code == 200
        body = response.json()
        assert "shareId" in body, "Response should include shareId"
        assert "createdAt" in body, "Response should include createdAt"

        assert isinstance(body["shareId"], str), "shareId should be a string"
        assert len(body["shareId"]) > 0, "shareId should not be empty"
        assert isinstance(body["createdAt"], (int, float)), "createdAt should be a number"


class TestGetShareRoute:
    """Test suite for GetShareRoute through FastAPI test client."""

    def test_get_share_route_handler(
        self, share_service, dynamodb_stubber, items_table_name, shares_table_name
    ):
        """Test get share route handler returns expected response."""
        app = ServiceProvider().app
        client = TestClient(app)

        share_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        item_id = "test-item-789"
        vault_id = "test-vault-456"
        user_id = "test-user-123"
        s3_key = f"vaults/{vault_id}/files/{item_id}/test"
        now = int(time.time())

        # Stub 1: atomic per-IP rate limit increment
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"attempt_count": {"N": "1"}}},
            {
                "TableName": shares_table_name,
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        # Stub 2: atomic global rate limit increment
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"attempt_count": {"N": "1"}}},
            {
                "TableName": shares_table_name,
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        # Stub 3: get_item on shares table (fetch share metadata)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "created_at": {"N": str(now)},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            expected_params={
                "TableName": shares_table_name,
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        # Stub 4: get_item on items table (fetch item to get S3 key)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": vault_id},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": s3_key},
                    "encrypted_metadata": {"B": b"encrypted-meta"},
                }
            },
            expected_params={
                "TableName": items_table_name,
                "Key": {"PK": f"ITEM#{item_id}"},
            },
        )

        # Stub 5: update_item on shares table (increment access count)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "access_count": {"N": "1"},
                    "last_accessed_at": {"N": str(now)},
                }
            },
            {
                "TableName": shares_table_name,
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = client.get(f"/v1/shares/{share_id}")

        assert response.status_code == 200
        body = response.json()
        assert "shareId" in body, "Response should include shareId"
        assert "itemId" in body, "Response should include itemId"
        assert "downloadUrl" in body, "Response should include downloadUrl"
        assert "urlExpiresAt" in body, "Response should include urlExpiresAt"

        assert body["shareId"] == share_id
        assert body["itemId"] == item_id
        assert isinstance(body["downloadUrl"], str), "downloadUrl should be a string"
        assert s3_key in body["downloadUrl"], "downloadUrl should contain the S3 key"
        assert isinstance(body["urlExpiresAt"], (int, float)), "urlExpiresAt should be a number"


class TestRevokeShareRoute:
    """Test suite for RevokeShareRoute through FastAPI test client."""

    def test_revoke_share_route_handler(self, client, dynamodb_stubber, shares_table_name):
        """Test revoke share route handler returns expected response."""
        share_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        user_id = "test-user-id"
        item_id = "test-item-789"
        vault_id = "test-vault-456"
        now = int(time.time())

        # Stub 1: get_item on shares table (fetch share metadata for ownership check)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "created_at": {"N": str(now)},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                }
            },
            expected_params={
                "TableName": shares_table_name,
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        # Stub 2: update_item on shares table (set is_revoked and ttl)
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "is_revoked": {"BOOL": True},
                    "ttl": {"N": str(now + 604800)},
                }
            },
            {
                "TableName": shares_table_name,
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = client.delete(f"/v1/shares/{share_id}")

        assert response.status_code == 200
        body = response.json()
        assert "message" in body, "Response should include message"
        assert "revokedAt" in body, "Response should include revokedAt"

        assert body["message"] == "Share revoked successfully"
        assert isinstance(body["revokedAt"], (int, float)), "revokedAt should be a number"


class TestGetShareRouteErrors:
    """Test suite for error handling in GetShareRoute."""

    def test_get_share_rate_limited_returns_429(self, dynamodb_stubber, shares_table_name):
        """Per-IP rate limit exceeded should map to HTTP 429 with Retry-After."""
        app = ServiceProvider().app
        # GET /v1/shares/{id} is a public (anonymous) endpoint — no auth override needed
        client = TestClient(app)
        share_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"attempt_count": {"N": "6"}}},
            {
                "TableName": shares_table_name,
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = client.get(f"/v1/shares/{share_id}")

        assert response.status_code == 429
        assert "retry-after" in {k.lower() for k in response.headers}
        assert int(response.headers["retry-after"]) > 0
        assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    def test_get_share_revoked_returns_410(self, dynamodb_stubber, shares_table_name):
        """A revoked share should map to HTTP 410 with a structured error body."""
        app = ServiceProvider().app
        # GET /v1/shares/{id} is a public (anonymous) endpoint — no auth override needed
        client = TestClient(app)
        share_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        now = int(time.time())

        for _ in range(2):
            dynamodb_stubber.add_response(
                "update_item",
                {"Attributes": {"attempt_count": {"N": "1"}}},
                {
                    "TableName": shares_table_name,
                    "Key": ANY,
                    "UpdateExpression": ANY,
                    "ExpressionAttributeValues": ANY,
                    "ExpressionAttributeNames": ANY,
                    "ReturnValues": "ALL_NEW",
                },
            )

        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "test-item-789"},
                    "user_id": {"S": "test-user-123"},
                    "created_at": {"N": str(now)},
                    "is_revoked": {"BOOL": True},
                    "access_count": {"N": "0"},
                }
            },
            expected_params={
                "TableName": shares_table_name,
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        response = client.get(f"/v1/shares/{share_id}")

        assert response.status_code == 410
        assert response.json()["error"]["code"] == "SHARE_REVOKED"
