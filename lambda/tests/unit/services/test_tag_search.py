"""
Unit tests for tag search functionality.

Requirements: 11.4, 11.5
"""

from base64 import b64encode

import pytest
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from botocore.stub import ANY


class TestTagSearch:
    """Test tag search using tag index rows."""

    def test_search_by_tag_returns_matching_items(self, item_service, dynamodb_stubber):
        """Should query tag index and batch get full item metadata."""
        vault_id = "vault-123"
        encrypted_tag = b"encrypted-tag-value"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()
        tag_pk = f"VAULT#{vault_id}#TAG#{encrypted_tag_b64}"

        # Stub 1: Query tag index rows
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": tag_pk},
                        "SK": {"S": "ITEM#item-1"},
                        "item_id": {"S": "item-1"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                    },
                    {
                        "PK": {"S": tag_pk},
                        "SK": {"S": "ITEM#item-3"},
                        "item_id": {"S": "item-3"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                    },
                ],
                "Count": 2,
            },
            {
                "TableName": "test-items-table",
                "KeyConditionExpression": "PK = :tag_pk",
                "ExpressionAttributeValues": {":tag_pk": tag_pk},
                "Limit": 50,
                "ScanIndexForward": True,
            },
        )

        # Stub 2: Batch get full item metadata
        dynamodb_stubber.add_response(
            "batch_get_item",
            {
                "Responses": {
                    "test-items-table": [
                        {
                            "PK": {"S": "ITEM#item-1"},
                            "SK": {"S": "METADATA"},
                            "item_id": {"S": "item-1"},
                            "item_type": {"S": "NOTE"},
                            "vault_id": {"S": vault_id},
                            "user_id": {"S": "user-123"},
                            "encrypted_metadata": {"B": b"metadata-1"},
                            "encrypted_tags": {"L": [{"B": encrypted_tag}]},
                            "encrypted_content": {"B": b"content-1"},
                            "created_at": {"N": "1234567890"},
                            "updated_at": {"N": "1234567890"},
                            "version": {"N": "1"},
                        },
                        {
                            "PK": {"S": "ITEM#item-3"},
                            "SK": {"S": "METADATA"},
                            "item_id": {"S": "item-3"},
                            "item_type": {"S": "EVENT"},
                            "vault_id": {"S": vault_id},
                            "user_id": {"S": "user-123"},
                            "encrypted_metadata": {"B": b"metadata-3"},
                            "encrypted_tags": {"L": [{"B": encrypted_tag}]},
                            "encrypted_content": {"B": b"content-3"},
                            "created_at": {"N": "1234567892"},
                            "updated_at": {"N": "1234567892"},
                            "version": {"N": "1"},
                        },
                    ]
                },
                "UnprocessedKeys": {},
            },
            {"RequestItems": ANY},
        )

        response = item_service.search_by_tag(
            vault_id=vault_id,
            encrypted_tag=encrypted_tag_b64,
            page_size=50,
        )

        assert len(response.items) == 2
        item_ids = {item.item_id for item in response.items}
        assert item_ids == {"item-1", "item-3"}
        assert response.next_token is None

    def test_search_by_tag_with_no_matches(self, item_service, dynamodb_stubber):
        """Should return empty list when tag index has no entries."""
        vault_id = "vault-123"
        encrypted_tag = b"non-existent-tag"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()
        tag_pk = f"VAULT#{vault_id}#TAG#{encrypted_tag_b64}"

        # Stub: Empty tag index query
        dynamodb_stubber.add_response(
            "query",
            {"Items": [], "Count": 0},
            {
                "TableName": "test-items-table",
                "KeyConditionExpression": "PK = :tag_pk",
                "ExpressionAttributeValues": {":tag_pk": tag_pk},
                "Limit": 50,
                "ScanIndexForward": True,
            },
        )

        response = item_service.search_by_tag(
            vault_id=vault_id,
            encrypted_tag=encrypted_tag_b64,
            page_size=50,
        )

        assert len(response.items) == 0
        assert response.next_token is None

    def test_search_by_tag_with_pagination(self, item_service, dynamodb_stubber):
        """Should return pagination token when more results available."""
        vault_id = "vault-123"
        encrypted_tag = b"popular-tag"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()
        tag_pk = f"VAULT#{vault_id}#TAG#{encrypted_tag_b64}"

        last_key = {"PK": {"S": tag_pk}, "SK": {"S": "ITEM#item-2"}}

        # Stub: Query returns page_size items with LastEvaluatedKey
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": tag_pk},
                        "SK": {"S": "ITEM#item-1"},
                        "item_id": {"S": "item-1"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                    },
                    {
                        "PK": {"S": tag_pk},
                        "SK": {"S": "ITEM#item-2"},
                        "item_id": {"S": "item-2"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                    },
                ],
                "Count": 2,
                "LastEvaluatedKey": last_key,
            },
            {
                "TableName": "test-items-table",
                "KeyConditionExpression": "PK = :tag_pk",
                "ExpressionAttributeValues": {":tag_pk": tag_pk},
                "Limit": 2,
                "ScanIndexForward": True,
            },
        )

        # Stub: Batch get for the 2 items
        dynamodb_stubber.add_response(
            "batch_get_item",
            {
                "Responses": {
                    "test-items-table": [
                        {
                            "PK": {"S": "ITEM#item-1"},
                            "SK": {"S": "METADATA"},
                            "item_id": {"S": "item-1"},
                            "item_type": {"S": "NOTE"},
                            "vault_id": {"S": vault_id},
                            "user_id": {"S": "user-123"},
                            "encrypted_metadata": {"B": b"m1"},
                            "encrypted_content": {"B": b"c1"},
                            "created_at": {"N": "1234567890"},
                            "updated_at": {"N": "1234567890"},
                            "version": {"N": "1"},
                        },
                        {
                            "PK": {"S": "ITEM#item-2"},
                            "SK": {"S": "METADATA"},
                            "item_id": {"S": "item-2"},
                            "item_type": {"S": "NOTE"},
                            "vault_id": {"S": vault_id},
                            "user_id": {"S": "user-123"},
                            "encrypted_metadata": {"B": b"m2"},
                            "encrypted_content": {"B": b"c2"},
                            "created_at": {"N": "1234567891"},
                            "updated_at": {"N": "1234567891"},
                            "version": {"N": "1"},
                        },
                    ]
                },
                "UnprocessedKeys": {},
            },
            {"RequestItems": ANY},
        )

        response = item_service.search_by_tag(
            vault_id=vault_id,
            encrypted_tag=encrypted_tag_b64,
            page_size=2,
        )

        assert len(response.items) == 2
        assert response.next_token is not None

    def test_search_by_tag_invalid_base64(self, item_service):
        """Should raise BadRequestError for invalid base64 tag."""
        with pytest.raises(BadRequestError, match="Invalid encrypted_tag"):
            item_service.search_by_tag(
                vault_id="vault-123",
                encrypted_tag="not-valid-base64!!!",
            )
