"""
Unit tests for share route handlers.

Tests verify that share routes work correctly through the lambda handler entrypoint.
"""

import json
import time

from botocore.stub import ANY

from src.entrypoint.api import lambda_handler


class TestCreateShareRoute:
    """Test suite for CreateShareRoute through lambda handler."""

    def test_create_share_route_handler(
        self, mock_service_provider, dynamodb_stubber, items_table_name, shares_table_name
    ):
        """Test create share route handler returns expected response."""
        user_id = "test-user-123"
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

        event = {
            "resource": "/v1/shares",
            "path": "/v1/shares",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"item_id": item_id}),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "share_id" in body, "Response should include share_id"
        assert "created_at" in body, "Response should include created_at"

        # Validate response values
        assert isinstance(body["share_id"], str), "share_id should be a string"
        assert len(body["share_id"]) > 0, "share_id should not be empty"
        assert isinstance(body["created_at"], int), "created_at should be an integer"


class TestGetShareRoute:
    """Test suite for GetShareRoute through lambda handler."""

    def test_get_share_route_handler(
        self, mock_service_provider, dynamodb_stubber, items_table_name, shares_table_name
    ):
        """Test get share route handler returns expected response."""
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

        event = {
            "resource": "/v1/shares/{share_id}",
            "path": f"/v1/shares/{share_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"share_id": share_id},
            "requestContext": {
                "requestId": "test-request-id",
                "identity": {"sourceIp": "1.2.3.4"},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "share_id" in body, "Response should include share_id"
        assert "item_id" in body, "Response should include item_id"
        assert "download_url" in body, "Response should include download_url"
        assert "url_expires_at" in body, "Response should include url_expires_at"

        # Validate response values
        assert body["share_id"] == share_id
        assert body["item_id"] == item_id
        assert isinstance(body["download_url"], str), "download_url should be a string"
        assert s3_key in body["download_url"], "download_url should contain the S3 key"
        assert isinstance(body["url_expires_at"], int), "url_expires_at should be an integer"


class TestRevokeShareRoute:
    """Test suite for RevokeShareRoute through lambda handler."""

    def test_revoke_share_route_handler(
        self, mock_service_provider, dynamodb_stubber, shares_table_name
    ):
        """Test revoke share route handler returns expected response."""
        share_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        user_id = "test-user-123"
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

        event = {
            "resource": "/v1/shares/{share_id}",
            "path": f"/v1/shares/{share_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"share_id": share_id},
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": user_id}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "message" in body, "Response should include message"
        assert "revoked_at" in body, "Response should include revoked_at"

        # Validate response values
        assert body["message"] == "Share revoked successfully"
        assert isinstance(body["revoked_at"], int), "revoked_at should be an integer"
