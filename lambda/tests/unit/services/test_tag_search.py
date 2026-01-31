"""
Unit tests for tag search functionality.

Requirements: 11.4, 11.5
"""

from base64 import b64encode


class TestTagSearch:
    """Test tag search functionality."""

    def test_search_by_tag_returns_matching_items(
        self, item_service, dynamodb_stubber, dynamodb_resource
    ):
        """Should return items that have the specified encrypted tag."""
        vault_id = "vault-123"
        encrypted_tag = b"encrypted-tag-value"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()

        # Mock DynamoDB query response with items that have matching tags
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "ITEM#item-1"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "NOTE"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-1"},
                        "encrypted_tags": {"L": [{"B": encrypted_tag}, {"B": b"other-tag"}]},
                        "encrypted_content": {"B": b"encrypted-content-1"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    },
                    {
                        "PK": {"S": "ITEM#item-2"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-2"},
                        "item_type": {"S": "TASK"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-2"},
                        "encrypted_tags": {"L": [{"B": b"different-tag"}]},
                        "encrypted_content": {"B": b"encrypted-content-2"},
                        "created_at": {"N": "1234567891"},
                        "updated_at": {"N": "1234567891"},
                        "version": {"N": "1"},
                    },
                    {
                        "PK": {"S": "ITEM#item-3"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-3"},
                        "item_type": {"S": "EVENT"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-3"},
                        "encrypted_tags": {"L": [{"B": encrypted_tag}]},
                        "encrypted_content": {"B": b"encrypted-content-3"},
                        "created_at": {"N": "1234567892"},
                        "updated_at": {"N": "1234567892"},
                        "version": {"N": "1"},
                    },
                ],
                "Count": 3,
            },
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": "GSI2PK = :vault_pk",
                "ExpressionAttributeValues": {":vault_pk": f"VAULT#{vault_id}"},
                "Limit": 250,
                "ScanIndexForward": True,
            },
        )

        # Execute search
        with dynamodb_stubber:
            response = item_service.search_by_tag(
                vault_id=vault_id,
                encrypted_tag=encrypted_tag_b64,
                page_size=50,
            )

        # Verify results
        assert len(response.items) == 2  # Only items 1 and 3 have the matching tag
        assert response.items[0].item_id == "item-1"
        assert response.items[0].item_type == "NOTE"
        assert response.items[1].item_id == "item-3"
        assert response.items[1].item_type == "EVENT"
        assert response.next_token is None

    def test_search_by_tag_with_no_matches(self, item_service, dynamodb_stubber):
        """Should return empty list when no items have the specified tag."""
        vault_id = "vault-123"
        encrypted_tag = b"non-existent-tag"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()

        # Mock DynamoDB query response with items that don't have matching tags
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "ITEM#item-1"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "NOTE"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-1"},
                        "encrypted_tags": {"L": [{"B": b"different-tag"}]},
                        "encrypted_content": {"B": b"encrypted-content-1"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    },
                ],
                "Count": 1,
            },
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": "GSI2PK = :vault_pk",
                "ExpressionAttributeValues": {":vault_pk": f"VAULT#{vault_id}"},
                "Limit": 250,
                "ScanIndexForward": True,
            },
        )

        # Execute search
        with dynamodb_stubber:
            response = item_service.search_by_tag(
                vault_id=vault_id,
                encrypted_tag=encrypted_tag_b64,
                page_size=50,
            )

        # Verify results
        assert len(response.items) == 0
        assert response.next_token is None

    def test_search_by_tag_filters_items_without_tags(self, item_service, dynamodb_stubber):
        """Should skip items that don't have any tags."""
        vault_id = "vault-123"
        encrypted_tag = b"encrypted-tag-value"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()

        # Mock DynamoDB query response with items, some without tags
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": "ITEM#item-1"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-1"},
                        "item_type": {"S": "NOTE"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-1"},
                        # No encrypted_tags field
                        "encrypted_content": {"B": b"encrypted-content-1"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "version": {"N": "1"},
                    },
                    {
                        "PK": {"S": "ITEM#item-2"},
                        "SK": {"S": "METADATA"},
                        "item_id": {"S": "item-2"},
                        "item_type": {"S": "TASK"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": "user-123"},
                        "encrypted_metadata": {"B": b"encrypted-metadata-2"},
                        "encrypted_tags": {"L": [{"B": encrypted_tag}]},
                        "encrypted_content": {"B": b"encrypted-content-2"},
                        "created_at": {"N": "1234567891"},
                        "updated_at": {"N": "1234567891"},
                        "version": {"N": "1"},
                    },
                ],
                "Count": 2,
            },
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": "GSI2PK = :vault_pk",
                "ExpressionAttributeValues": {":vault_pk": f"VAULT#{vault_id}"},
                "Limit": 250,
                "ScanIndexForward": True,
            },
        )

        # Execute search
        with dynamodb_stubber:
            response = item_service.search_by_tag(
                vault_id=vault_id,
                encrypted_tag=encrypted_tag_b64,
                page_size=50,
            )

        # Verify results - only item-2 should be returned
        assert len(response.items) == 1
        assert response.items[0].item_id == "item-2"

    def test_search_by_tag_respects_page_size(self, item_service, dynamodb_stubber):
        """Should limit results to the specified page size."""
        vault_id = "vault-123"
        encrypted_tag = b"encrypted-tag-value"
        encrypted_tag_b64 = b64encode(encrypted_tag).decode()

        # Create 5 items with matching tags
        items = []
        for i in range(5):
            items.append(
                {
                    "PK": {"S": f"ITEM#item-{i}"},
                    "SK": {"S": "METADATA"},
                    "item_id": {"S": f"item-{i}"},
                    "item_type": {"S": "NOTE"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": "user-123"},
                    "encrypted_metadata": {"B": f"encrypted-metadata-{i}".encode()},
                    "encrypted_tags": {"L": [{"B": encrypted_tag}]},
                    "encrypted_content": {"B": f"encrypted-content-{i}".encode()},
                    "created_at": {"N": str(1234567890 + i)},
                    "updated_at": {"N": str(1234567890 + i)},
                    "version": {"N": "1"},
                }
            )

        # Mock DynamoDB query response
        dynamodb_stubber.add_response(
            "query",
            {"Items": items, "Count": 5},
            {
                "TableName": "test-items-table",
                "IndexName": "GSI2",
                "KeyConditionExpression": "GSI2PK = :vault_pk",
                "ExpressionAttributeValues": {":vault_pk": f"VAULT#{vault_id}"},
                "Limit": 10,
                "ScanIndexForward": True,
            },
        )

        # Execute search with page_size=2
        with dynamodb_stubber:
            response = item_service.search_by_tag(
                vault_id=vault_id,
                encrypted_tag=encrypted_tag_b64,
                page_size=2,
            )

        # Verify results - should only return 2 items
        assert len(response.items) == 2
        # Note: next_token behavior depends on whether DynamoDB returns LastEvaluatedKey
        # In this test, all items are returned in one query, so next_token is generated
        # based on having more matching items than page_size
        assert response.next_token is not None  # More results available
