"""
Unit tests for tag route handlers.

Tests verify that tag routes work correctly through the FastAPI test client.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.environment.service_provider import ServiceProvider
from src.shared.auth import get_current_user
from src.shared.models import ItemMetadata, SearchByTagResponse


def _make_tag_client(vault_service_mock, item_service_mock):
    """Create a test client with mocked tag dependencies."""
    sp = ServiceProvider()
    # Replace the tag route's services with mocks
    sp.__dict__["item_service"] = item_service_mock
    sp.__dict__["vault_service"] = vault_service_mock
    app = sp.app
    app.dependency_overrides[get_current_user] = lambda: "user-123"
    return TestClient(app)


class TestSearchTagsRoute:
    """Test suite for SearchTagsRoute through FastAPI test client."""

    def test_search_tags_route_handler_missing_vault_id(self, client):
        """Test search tags route handler returns 422 when vault_id is missing."""
        response = client.get(
            "/v1/tags/search",
            params={"encrypted_tag": "dGVzdC10YWc="},
        )

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422

    def test_search_tags_route_handler_missing_encrypted_tag(self, client):
        """Test search tags route handler returns 422 when encrypted_tag is missing."""
        response = client.get(
            "/v1/tags/search",
            params={"vault_id": "vault-123"},
        )

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422

    def test_search_tags_route_handler_invalid_page_size(self, client):
        """Test search tags route handler returns 422 when page_size is invalid."""
        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
                "page_size": "200",  # Invalid: > 100
            },
        )

        # FastAPI returns 422 for invalid query param values
        assert response.status_code == 422

    def test_search_tags_route_handler_invalid_vault(self):
        """Test search tags route handler returns 400 when vault doesn't exist."""
        vault_service_mock = MagicMock()
        vault_service_mock.vault_exists = MagicMock(return_value=False)
        item_service_mock = MagicMock()

        client = _make_tag_client(vault_service_mock, item_service_mock)

        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "invalid-vault",
                "encrypted_tag": "dGVzdC10YWc=",
            },
        )

        assert response.status_code == 400
        body = response.json()
        assert "message" in body

    def test_search_tags_route_handler_success(self):
        """Test search tags route handler returns matching items."""
        vault_service_mock = MagicMock()
        vault_service_mock.vault_exists = MagicMock(return_value=True)

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
        item_service_mock = MagicMock()
        item_service_mock.search_by_tag = MagicMock(return_value=mock_response)

        client = _make_tag_client(vault_service_mock, item_service_mock)

        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert len(body["items"]) == 1
        assert body["items"][0]["item_id"] == "item-1"
        assert body["items"][0]["item_type"] == "NOTE"
        assert "encrypted_metadata" in body["items"][0]
        assert "encrypted_tags" in body["items"][0]
        assert "created_at" in body["items"][0]
        assert "updated_at" in body["items"][0]
        assert "version" in body["items"][0]

    def test_search_tags_route_handler_success_with_media_item(self):
        """Test search tags route handler includes s3_key and size_bytes for media items."""
        vault_service_mock = MagicMock()
        vault_service_mock.vault_exists = MagicMock(return_value=True)

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
        item_service_mock = MagicMock()
        item_service_mock.search_by_tag = MagicMock(return_value=mock_response)

        client = _make_tag_client(vault_service_mock, item_service_mock)

        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert len(body["items"]) == 1
        assert body["items"][0]["s3_key"] == "vaults/vault-123/files/item-1/file.jpg"
        assert body["items"][0]["size_bytes"] == 1024

    def test_search_tags_route_handler_success_with_pagination(self):
        """Test search tags route handler includes next_token when present."""
        vault_service_mock = MagicMock()
        vault_service_mock.vault_exists = MagicMock(return_value=True)

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
        item_service_mock = MagicMock()
        item_service_mock.search_by_tag = MagicMock(return_value=mock_response)

        client = _make_tag_client(vault_service_mock, item_service_mock)

        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
                "page_size": "10",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "next_token" in body
        assert body["next_token"] == "next-page-token"

    def test_search_tags_route_handler_success_empty_results(self):
        """Test search tags route handler returns empty items list when no matches."""
        vault_service_mock = MagicMock()
        vault_service_mock.vault_exists = MagicMock(return_value=True)

        mock_response = SearchByTagResponse(items=[], next_token=None)
        item_service_mock = MagicMock()
        item_service_mock.search_by_tag = MagicMock(return_value=mock_response)

        client = _make_tag_client(vault_service_mock, item_service_mock)

        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert len(body["items"]) == 0
        assert "next_token" not in body

    def test_search_tags_route_handler_success_no_tags(self):
        """Test search tags route handler handles items with no tags."""
        vault_service_mock = MagicMock()
        vault_service_mock.vault_exists = MagicMock(return_value=True)

        now = datetime.now(tz=timezone.utc)
        mock_items = [
            ItemMetadata(
                item_id="item-1",
                item_type="NOTE",
                vault_id="vault-123",
                user_id="user-123",
                encrypted_content=b"encrypted-content",
                encrypted_metadata=b"encrypted-metadata",
                encrypted_tags=None,
                created_at=now,
                updated_at=now,
                version=1,
                size_bytes=None,
                s3_key=None,
            ),
        ]
        mock_response = SearchByTagResponse(items=mock_items, next_token=None)
        item_service_mock = MagicMock()
        item_service_mock.search_by_tag = MagicMock(return_value=mock_response)

        client = _make_tag_client(vault_service_mock, item_service_mock)

        response = client.get(
            "/v1/tags/search",
            params={
                "vault_id": "vault-123",
                "encrypted_tag": "dGVzdC10YWc=",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert len(body["items"]) == 1
        assert body["items"][0]["encrypted_tags"] is None
