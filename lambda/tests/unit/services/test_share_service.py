"""
Unit tests for ShareService.

Tests the share service layer for creating shares, accessing shared items,
revoking shares, and rate limiting.

Schema: PK: SHARE#{shareId}, SK: METADATA (share metadata)
        PK: SHARE#{shareId}, SK: RATE#{ipAddress} (rate limit)
"""

import time
from unittest.mock import patch

import pytest
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from botocore.stub import ANY

from src.api.services.share_service import (
    RateLimitExceededError,
    ShareExpiredError,
    ShareRevokedError,
)
from src.shared.models import CreateShareRequest


class TestCreateShare:
    """Tests for create_share method."""

    def test_create_share_success(self, share_service, dynamodb_stubber):
        """Test creating a share for an owned item."""
        item_id = "item-123"
        user_id = "user-123"

        # Stub get_item for items table (verify ownership)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": "vault-123"},
                    "item_type": {"S": "MEDIA"},
                    "s3_key": {"S": f"vaults/vault-123/files/{item_id}/test"},
                    "encrypted_metadata": {"B": b"encrypted-metadata"},
                }
            },
            {"TableName": "test-items-table", "Key": {"PK": f"ITEM#{item_id}"}},
        )

        # Stub put_item for shares table
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-shares-table", "Item": ANY}
        )

        request = CreateShareRequest(item_id=item_id)
        response = share_service.create_share(user_id, request)

        assert response.share_id is not None
        assert len(response.share_id) > 0
        assert response.created_at > 0
        assert response.expires_at is None

    def test_create_share_with_expiration(self, share_service, dynamodb_stubber):
        """Test creating a share with an expiration timestamp."""
        item_id = "item-123"
        user_id = "user-123"
        expires_at = int(time.time()) + 86400  # 24 hours from now

        # Stub get_item for items table
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": "vault-123"},
                    "item_type": {"S": "MEDIA"},
                }
            },
            {"TableName": "test-items-table", "Key": {"PK": f"ITEM#{item_id}"}},
        )

        # Stub put_item for shares table
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-shares-table", "Item": ANY}
        )

        request = CreateShareRequest(item_id=item_id, expires_at=expires_at)
        response = share_service.create_share(user_id, request)

        assert response.share_id is not None
        assert response.expires_at == expires_at

    def test_create_share_item_not_found(self, share_service, dynamodb_stubber):
        """Test creating a share when item doesn't exist."""
        # Stub get_item returning empty (item not found)
        dynamodb_stubber.add_response(
            "get_item", {}, {"TableName": "test-items-table", "Key": ANY}
        )

        request = CreateShareRequest(item_id="nonexistent-item")

        with pytest.raises(NotFoundError, match="Item not found"):
            share_service.create_share("user-123", request)

    def test_create_share_wrong_owner(self, share_service, dynamodb_stubber):
        """Test creating a share for an item owned by a different user."""
        item_id = "item-123"

        # Stub get_item returning item owned by different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "other-user"},
                    "vault_id": {"S": "vault-123"},
                }
            },
            {"TableName": "test-items-table", "Key": {"PK": f"ITEM#{item_id}"}},
        )

        request = CreateShareRequest(item_id=item_id)

        with pytest.raises(NotFoundError, match="Item not found"):
            share_service.create_share("user-123", request)


class TestGetShare:
    """Tests for get_share method."""

    def test_get_share_success(self, share_service, dynamodb_stubber, s3_stubber, files_bucket_name):
        """Test successfully accessing a share."""
        share_id = "share-123"
        item_id = "item-456"
        client_ip = "192.168.1.1"
        s3_key = "vaults/vault-123/files/item-456/test"

        # Stub rate limit check (get_item returns empty = no prior attempts)
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": f"RATE#{client_ip}"},
            },
        )

        # Stub rate limit put_item (create new rate entry)
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-shares-table", "Item": ANY}
        )

        # Stub get share metadata
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "vault_id": {"S": "vault-123"},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        # Stub get item (for s3_key)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"ITEM#{item_id}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": item_id},
                    "user_id": {"S": "user-123"},
                    "vault_id": {"S": "vault-123"},
                    "s3_key": {"S": s3_key},
                    "item_type": {"S": "MEDIA"},
                }
            },
            {"TableName": "test-items-table", "Key": {"PK": f"ITEM#{item_id}"}},
        )

        # Stub update access count
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {}},
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = share_service.get_share(share_id, client_ip)

        assert response.share_id == share_id
        assert response.item_id == item_id
        assert response.download_url is not None
        assert response.url_expires_at > 0
        assert response.expires_at is None

    def test_get_share_revoked(self, share_service, dynamodb_stubber):
        """Test accessing a revoked share raises ShareRevokedError."""
        share_id = "share-123"
        client_ip = "192.168.1.1"

        # Stub rate limit check (no prior attempts)
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": f"RATE#{client_ip}"},
            },
        )

        # Stub rate limit put_item
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-shares-table", "Item": ANY}
        )

        # Stub get share metadata (revoked)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item-456"},
                    "user_id": {"S": "user-123"},
                    "vault_id": {"S": "vault-123"},
                    "is_revoked": {"BOOL": True},
                    "access_count": {"N": "5"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        with pytest.raises(ShareRevokedError):
            share_service.get_share(share_id, client_ip)

    def test_get_share_expired(self, share_service, dynamodb_stubber):
        """Test accessing an expired share raises ShareExpiredError."""
        share_id = "share-123"
        client_ip = "192.168.1.1"
        expired_time = int(time.time()) - 3600  # 1 hour ago

        # Stub rate limit check (no prior attempts)
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": f"RATE#{client_ip}"},
            },
        )

        # Stub rate limit put_item
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": "test-shares-table", "Item": ANY}
        )

        # Stub get share metadata (expired)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item-456"},
                    "user_id": {"S": "user-123"},
                    "vault_id": {"S": "vault-123"},
                    "is_revoked": {"BOOL": False},
                    "expires_at": {"N": str(expired_time)},
                    "access_count": {"N": "3"},
                    "created_at": {"N": str(expired_time - 86400)},
                }
            },
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        with pytest.raises(ShareExpiredError):
            share_service.get_share(share_id, client_ip)


class TestRevokeShare:
    """Tests for revoke_share method."""

    def test_revoke_share_success(self, share_service, dynamodb_stubber):
        """Test successfully revoking a share."""
        share_id = "share-123"
        user_id = "user-123"

        # Stub get share metadata
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item-456"},
                    "user_id": {"S": user_id},
                    "vault_id": {"S": "vault-123"},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "2"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        # Stub update_item (set is_revoked and ttl)
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {}},
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ExpressionAttributeNames": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = share_service.revoke_share(user_id, share_id)

        assert response.message == "Share revoked successfully"
        assert response.revoked_at > 0

    def test_revoke_share_wrong_owner(self, share_service, dynamodb_stubber):
        """Test revoking a share owned by a different user."""
        share_id = "share-123"

        # Stub get share metadata (owned by different user)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"SHARE#{share_id}"},
                    "SK": {"S": "METADATA"},
                    "share_id": {"S": share_id},
                    "item_id": {"S": "item-456"},
                    "user_id": {"S": "other-user"},
                    "vault_id": {"S": "vault-123"},
                    "is_revoked": {"BOOL": False},
                    "access_count": {"N": "0"},
                    "created_at": {"N": str(int(time.time()))},
                }
            },
            {
                "TableName": "test-shares-table",
                "Key": {"PK": f"SHARE#{share_id}", "SK": "METADATA"},
            },
        )

        with pytest.raises(NotFoundError, match="Share not found"):
            share_service.revoke_share("user-123", share_id)
