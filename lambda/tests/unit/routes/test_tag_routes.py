"""
Unit tests for tag route handlers.

Tests verify that tag routes work correctly through the lambda handler entrypoint.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.entrypoint.api import lambda_handler
from src.shared.models import ItemMetadata, SearchByTagResponse


class TestSearchTagsRoute:
    """Test suite for SearchTagsRoute through lambda handler."""

    def test_search_tags_route_handler_missing_vault_id(self, mock_service_provider):
        """Test search tags route handler returns 400 when vault_id is missing."""
        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "encrypted_tag": "dGVzdC10YWc=",  # base64 encoded
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 400

        # Verify error response
        body = json.loads(response["body"])
        assert "message" in body

    def test_search_tags_route_handler_missing_encrypted_tag(self, mock_service_provider):
        """Test search tags route handler returns 400 when encrypted_tag is missing."""
        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 400

        # Verify error response
        body = json.loads(response["body"])
        assert "message" in body

    def test_search_tags_route_handler_invalid_page_size(self, mock_service_provider):
        """Test search tags route handler returns 400 when page_size is invalid."""
        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
                "page_size": "200",  # Invalid: > 100
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 400

        # Verify error response
        body = json.loads(response["body"])
        assert "message" in body

    def test_search_tags_route_handler_invalid_vault(self, mock_service_provider):
        """Test search tags route handler returns 400 when vault doesn't exist."""
        # Mock vault_exists to return False
        mock_service_provider.vault_service.vault_exists = MagicMock(return_value=False)

        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "invalid-vault",
                "encrypted_tag": "dGVzdC10YWc=",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 400

        # Verify error response
        body = json.loads(response["body"])
        assert "message" in body

    def test_search_tags_route_handler_success(self, mock_service_provider):
        """Test search tags route handler returns matching items."""
        # Mock vault_exists to return True
        mock_service_provider.vault_service.vault_exists = MagicMock(return_value=True)

        # Create mock response with items
        now = datetime.now(tz=timezone.utc)
        mock_items = [
            ItemMetadata(
                item_id="item-1",
                item_type="NOTE",
                vault_id="vault-123",
                user_id="user-123",
                encrypted_content=b"encrypted-content",
                encrypted_metadata=b"encrypted-metadata",
                encrypted_tags=[b"encrypted-tag"],
                created_at=now,
                updated_at=now,
                version=1,
                size_bytes=None,
                s3_key=None,
            ),
        ]
        mock_response = SearchByTagResponse(items=mock_items, next_token=None)
        mock_service_provider.item_service.search_by_tag = MagicMock(return_value=mock_response)

        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response structure
        body = json.loads(response["body"])
        assert "items" in body
        assert len(body["items"]) == 1
        assert body["items"][0]["item_id"] == "item-1"
        assert body["items"][0]["item_type"] == "NOTE"
        assert "encrypted_metadata" in body["items"][0]
        assert "encrypted_tags" in body["items"][0]
        assert "created_at" in body["items"][0]
        assert "updated_at" in body["items"][0]
        assert "version" in body["items"][0]

    def test_search_tags_route_handler_success_with_media_item(self, mock_service_provider):
        """Test search tags route handler includes s3_key and size_bytes for media items."""
        # Mock vault_exists to return True
        mock_service_provider.vault_service.vault_exists = MagicMock(return_value=True)

        # Create mock response with media item
        now = datetime.now(tz=timezone.utc)
        mock_items = [
            ItemMetadata(
                item_id="item-1",
                item_type="MEDIA",
                vault_id="vault-123",
                user_id="user-123",
                encrypted_content=None,
                encrypted_metadata=b"encrypted-metadata",
                encrypted_tags=[b"encrypted-tag"],
                created_at=now,
                updated_at=now,
                version=1,
                size_bytes=1024,
                s3_key="vaults/vault-123/files/item-1/file.jpg",
            ),
        ]
        mock_response = SearchByTagResponse(items=mock_items, next_token=None)
        mock_service_provider.item_service.search_by_tag = MagicMock(return_value=mock_response)

        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response includes media-specific fields
        body = json.loads(response["body"])
        assert "items" in body
        assert len(body["items"]) == 1
        assert body["items"][0]["s3_key"] == "vaults/vault-123/files/item-1/file.jpg"
        assert body["items"][0]["size_bytes"] == 1024

    def test_search_tags_route_handler_success_with_pagination(self, mock_service_provider):
        """Test search tags route handler includes next_token when present."""
        # Mock vault_exists to return True
        mock_service_provider.vault_service.vault_exists = MagicMock(return_value=True)

        # Create mock response with pagination token
        now = datetime.now(tz=timezone.utc)
        mock_items = [
            ItemMetadata(
                item_id="item-1",
                item_type="NOTE",
                vault_id="vault-123",
                user_id="user-123",
                encrypted_content=b"encrypted-content",
                encrypted_metadata=b"encrypted-metadata",
                encrypted_tags=[b"encrypted-tag"],
                created_at=now,
                updated_at=now,
                version=1,
                size_bytes=None,
                s3_key=None,
            ),
        ]
        mock_response = SearchByTagResponse(items=mock_items, next_token="next-page-token")
        mock_service_provider.item_service.search_by_tag = MagicMock(return_value=mock_response)

        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
                "page_size": "10",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response includes next_token
        body = json.loads(response["body"])
        assert "next_token" in body
        assert body["next_token"] == "next-page-token"

    def test_search_tags_route_handler_success_empty_results(self, mock_service_provider):
        """Test search tags route handler returns empty items list when no matches."""
        # Mock vault_exists to return True
        mock_service_provider.vault_service.vault_exists = MagicMock(return_value=True)

        # Create mock response with no items
        mock_response = SearchByTagResponse(items=[], next_token=None)
        mock_service_provider.item_service.search_by_tag = MagicMock(return_value=mock_response)

        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify empty items list
        body = json.loads(response["body"])
        assert "items" in body
        assert len(body["items"]) == 0
        assert "next_token" not in body

    def test_search_tags_route_handler_success_no_tags(self, mock_service_provider):
        """Test search tags route handler handles items with no tags."""
        # Mock vault_exists to return True
        mock_service_provider.vault_service.vault_exists = MagicMock(return_value=True)

        # Create mock response with item that has no tags
        now = datetime.now(tz=timezone.utc)
        mock_items = [
            ItemMetadata(
                item_id="item-1",
                item_type="NOTE",
                vault_id="vault-123",
                user_id="user-123",
                encrypted_content=b"encrypted-content",
                encrypted_metadata=b"encrypted-metadata",
                encrypted_tags=None,  # No tags
                created_at=now,
                updated_at=now,
                version=1,
                size_bytes=None,
                s3_key=None,
            ),
        ]
        mock_response = SearchByTagResponse(items=mock_items, next_token=None)
        mock_service_provider.item_service.search_by_tag = MagicMock(return_value=mock_response)

        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "queryStringParameters": {
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response handles None tags
        body = json.loads(response["body"])
        assert "items" in body
        assert len(body["items"]) == 1
        assert body["items"][0]["encrypted_tags"] is None
