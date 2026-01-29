"""
Unit tests for collection service layer.

Tests verify collection CRUD operations and item-collection associations.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from aws_lambda_powertools.event_handler.exceptions import (
    ForbiddenError,
    InternalServerError,
    NotFoundError,
)
from botocore.stub import ANY

from src.api.services.collection_service import CollectionService
from src.shared.models import (
    AddItemToCollectionRequest,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)


@pytest.fixture
def collection_service(boto_session, collections_table_name, items_table_name):
    """Create collection service with stubbed boto3 session."""
    return CollectionService(
        session=boto_session,
        collections_table_name=collections_table_name,
        items_table_name=items_table_name,
    )


class TestCreateCollection:
    """Test suite for create_collection."""

    def test_create_collection_success(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test successful collection creation."""
        user_id = "user-123"
        vault_id = "vault-456"
        encrypted_metadata = b"encrypted-metadata"

        request = CreateCollectionRequest(
            vault_id=vault_id,
            encrypted_metadata=encrypted_metadata,
        )

        # Stub DynamoDB put_item
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": collections_table_name,
                "Item": ANY,
            },
        )

        response = collection_service.create_collection(user_id, request)

        assert response.collection_id is not None
        assert isinstance(response.created_at, datetime)

    def test_create_collection_storage_error(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test collection creation with storage error."""
        user_id = "user-123"
        vault_id = "vault-456"
        encrypted_metadata = b"encrypted-metadata"

        request = CreateCollectionRequest(
            vault_id=vault_id,
            encrypted_metadata=encrypted_metadata,
        )

        # Stub DynamoDB error
        dynamodb_stubber.add_client_error(
            "put_item",
            service_error_code="InternalServerError",
            service_message="Internal error",
        )

        with pytest.raises(InternalServerError):
            collection_service.create_collection(user_id, request)


class TestListCollections:
    """Test suite for list_collections."""

    def test_list_collections_success(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test successful collection listing."""
        user_id = "user-123"
        vault_id = "vault-456"

        # Stub DynamoDB query
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": f"VAULT#{vault_id}"},
                        "SK": {"S": "COLLECTION#col-1"},
                        "collection_id": {"S": "col-1"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": user_id},
                        "encrypted_metadata": {"B": b"metadata-1"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                        "item_count": {"N": "5"},
                    }
                ],
                "Count": 1,
            },
            {
                "TableName": collections_table_name,
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 50,
                "ScanIndexForward": False,
            },
        )

        collections, next_token = collection_service.list_collections(
            user_id=user_id,
            vault_id=vault_id,
            page_size=50,
        )

        assert len(collections) == 1
        assert collections[0]["collection_id"] == "col-1"
        assert collections[0]["item_count"] == 5
        assert next_token is None


class TestGetCollection:
    """Test suite for get_collection."""

    def test_get_collection_success(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test successful collection retrieval."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"

        # Stub DynamoDB get_item
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "3"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        collection = collection_service.get_collection(user_id, vault_id, collection_id)

        assert collection is not None
        assert collection["collection_id"] == collection_id
        assert collection["user_id"] == user_id

    def test_get_collection_not_found(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test collection not found."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"

        # Stub DynamoDB get_item with no result
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        collection = collection_service.get_collection(user_id, vault_id, collection_id)

        assert collection is None

    def test_get_collection_authorization_error(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test collection access denied for wrong user."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"

        # Stub DynamoDB get_item with different user
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": "different-user"},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "3"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        with pytest.raises(ForbiddenError):
            collection_service.get_collection(user_id, vault_id, collection_id)


class TestUpdateCollection:
    """Test suite for update_collection."""

    def test_update_collection_success(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test successful collection update."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"
        new_metadata = b"new-metadata"

        request = UpdateCollectionRequest(
            collection_id=collection_id,
            vault_id=vault_id,
            encrypted_metadata=new_metadata,
        )

        # Stub get_item for verification
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"old-metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "3"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub update_item
        dynamodb_stubber.add_response(
            "update_item",
            {
                "Attributes": {
                    "collection_id": {"S": collection_id},
                    "encrypted_metadata": {"B": new_metadata},
                    "updated_at": {"N": str(int(datetime.now(tz=timezone.utc).timestamp()))},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = collection_service.update_collection(user_id, request)

        assert response.collection_id == collection_id
        assert isinstance(response.updated_at, datetime)


class TestDeleteCollection:
    """Test suite for delete_collection."""

    def test_delete_collection_success(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test successful collection deletion with no associations."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"

        # Stub get_item for verification
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "0"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub query for associations (with pagination support)
        dynamodb_stubber.add_response(
            "query",
            {"Items": [], "Count": 0},
            {
                "TableName": collections_table_name,
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )

        # Stub delete_item
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        collection_service.delete_collection(user_id, vault_id, collection_id)

    def test_delete_collection_with_batch_associations(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test collection deletion with multiple associations using batch operations."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"

        # Stub get_item for verification
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "30"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Create 30 associations to test batch deletion (>25 items)
        associations = []
        for i in range(30):
            associations.append(
                {
                    "PK": {"S": f"COLLECTION#{collection_id}"},
                    "SK": {"S": f"ITEM#item-{i}"},
                    "collection_id": {"S": collection_id},
                    "item_id": {"S": f"item-{i}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "added_at": {"N": "1234567890"},
                }
            )

        # Stub query for associations (with pagination support)
        dynamodb_stubber.add_response(
            "query",
            {"Items": associations, "Count": 30},
            {
                "TableName": collections_table_name,
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )

        # Stub batch_write_item for first batch (25 items)
        dynamodb_stubber.add_response(
            "batch_write_item",
            {"UnprocessedItems": {}},
            {
                "RequestItems": {
                    collections_table_name: ANY,
                }
            },
        )

        # Stub batch_write_item for second batch (5 items)
        dynamodb_stubber.add_response(
            "batch_write_item",
            {"UnprocessedItems": {}},
            {
                "RequestItems": {
                    collections_table_name: ANY,
                }
            },
        )

        # Stub delete_item for collection metadata
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        collection_service.delete_collection(user_id, vault_id, collection_id)

    def test_delete_collection_with_pagination(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test collection deletion with pagination (>100 associations)."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"

        # Stub get_item for verification
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "150"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # First page: 100 associations
        first_page_associations = []
        for i in range(100):
            first_page_associations.append(
                {
                    "PK": {"S": f"COLLECTION#{collection_id}"},
                    "SK": {"S": f"ITEM#item-{i}"},
                    "collection_id": {"S": collection_id},
                    "item_id": {"S": f"item-{i}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "added_at": {"N": "1234567890"},
                }
            )

        # Stub first query (returns 100 items with LastEvaluatedKey)
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": first_page_associations,
                "Count": 100,
                "LastEvaluatedKey": {
                    "PK": {"S": f"COLLECTION#{collection_id}"},
                    "SK": {"S": "ITEM#item-99"},
                },
            },
            {
                "TableName": collections_table_name,
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 100,
                "ScanIndexForward": True,
            },
        )

        # Stub batch_write_item for first page (4 batches of 25 items each)
        for _ in range(4):
            dynamodb_stubber.add_response(
                "batch_write_item",
                {"UnprocessedItems": {}},
                {
                    "RequestItems": {
                        collections_table_name: ANY,
                    }
                },
            )

        # Second page: 50 associations
        second_page_associations = []
        for i in range(100, 150):
            second_page_associations.append(
                {
                    "PK": {"S": f"COLLECTION#{collection_id}"},
                    "SK": {"S": f"ITEM#item-{i}"},
                    "collection_id": {"S": collection_id},
                    "item_id": {"S": f"item-{i}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "added_at": {"N": "1234567890"},
                }
            )

        # Stub second query (returns 50 items, no LastEvaluatedKey)
        dynamodb_stubber.add_response(
            "query",
            {"Items": second_page_associations, "Count": 50},
            {
                "TableName": collections_table_name,
                "KeyConditionExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 100,
                "ExclusiveStartKey": ANY,
                "ScanIndexForward": True,
            },
        )

        # Stub batch_write_item for second page (2 batches: 25 + 25)
        for _ in range(2):
            dynamodb_stubber.add_response(
                "batch_write_item",
                {"UnprocessedItems": {}},
                {
                    "RequestItems": {
                        collections_table_name: ANY,
                    }
                },
            )

        # Stub delete_item for collection metadata
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        collection_service.delete_collection(user_id, vault_id, collection_id)


class TestAddItemToCollection:
    """Test suite for add_item_to_collection."""

    def test_add_item_to_collection_success(
        self,
        collection_service,
        dynamodb_stubber,
        collections_table_name,
        items_table_name,
    ):
        """Test successfully adding item to collection."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"
        item_id = "item-abc"

        request = AddItemToCollectionRequest(
            collection_id=collection_id,
            item_id=item_id,
            vault_id=vault_id,
        )

        # Stub get collection
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "0"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub query to find item by ID (single query with filter)
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": f"VAULT#{vault_id}"},
                        "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                        "item_id": {"S": item_id},
                        "item_type": {"S": "MEDIA"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": user_id},
                        "encrypted_metadata": {"B": b"item-metadata"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                    }
                ],
                "Count": 1,
            },
            {
                "TableName": items_table_name,
                "KeyConditionExpression": ANY,
                "FilterExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 1,
                "ScanIndexForward": True,
            },
        )

        # Stub put association with conditional expression
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": collections_table_name,
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )

        # Stub update item count
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"item_count": {"N": "1"}}},
            {
                "TableName": collections_table_name,
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        response = collection_service.add_item_to_collection(user_id, request)

        assert response.collection_id == collection_id
        assert response.item_id == item_id

    def test_add_item_to_collection_idempotent(
        self,
        collection_service,
        dynamodb_stubber,
        collections_table_name,
        items_table_name,
    ):
        """Test adding same item twice is idempotent (no duplicate count increment)."""

        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"
        item_id = "item-abc"

        request = AddItemToCollectionRequest(
            collection_id=collection_id,
            item_id=item_id,
            vault_id=vault_id,
        )

        # Stub get collection
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "1"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub query to find item by ID (single query with filter)
        dynamodb_stubber.add_response(
            "query",
            {
                "Items": [
                    {
                        "PK": {"S": f"VAULT#{vault_id}"},
                        "SK": {"S": f"ITEM#MEDIA#{item_id}"},
                        "item_id": {"S": item_id},
                        "item_type": {"S": "MEDIA"},
                        "vault_id": {"S": vault_id},
                        "user_id": {"S": user_id},
                        "encrypted_metadata": {"B": b"item-metadata"},
                        "created_at": {"N": "1234567890"},
                        "updated_at": {"N": "1234567890"},
                    }
                ],
                "Count": 1,
            },
            {
                "TableName": items_table_name,
                "KeyConditionExpression": ANY,
                "FilterExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "Limit": 1,
                "ScanIndexForward": True,
            },
        )

        # Stub put association - simulate conditional check failure (item already exists)
        dynamodb_stubber.add_client_error(
            "put_item",
            service_error_code="ConditionalCheckFailedException",
            service_message="The conditional request failed",
            expected_params={
                "TableName": collections_table_name,
                "Item": ANY,
                "ConditionExpression": ANY,
            },
        )

        response = collection_service.add_item_to_collection(user_id, request)

        # Should return success without incrementing count
        assert response.collection_id == collection_id
        assert response.item_id == item_id


class TestRemoveItemFromCollection:
    """Test suite for remove_item_from_collection."""

    def test_remove_item_from_collection_success(
        self, collection_service, dynamodb_stubber, collections_table_name
    ):
        """Test successfully removing item from collection."""
        user_id = "user-123"
        vault_id = "vault-456"
        collection_id = "col-789"
        item_id = "item-abc"

        # Stub get collection
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"VAULT#{vault_id}"},
                    "SK": {"S": f"COLLECTION#{collection_id}"},
                    "collection_id": {"S": collection_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "encrypted_metadata": {"B": b"metadata"},
                    "created_at": {"N": "1234567890"},
                    "updated_at": {"N": "1234567890"},
                    "item_count": {"N": "1"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub get association
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"COLLECTION#{collection_id}"},
                    "SK": {"S": f"ITEM#{item_id}"},
                    "collection_id": {"S": collection_id},
                    "item_id": {"S": item_id},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                    "added_at": {"N": "1234567890"},
                }
            },
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub delete association
        dynamodb_stubber.add_response(
            "delete_item",
            {},
            {
                "TableName": collections_table_name,
                "Key": ANY,
            },
        )

        # Stub update item count
        dynamodb_stubber.add_response(
            "update_item",
            {"Attributes": {"item_count": {"N": "0"}}},
            {
                "TableName": collections_table_name,
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
                "ReturnValues": "ALL_NEW",
            },
        )

        collection_service.remove_item_from_collection(user_id, vault_id, collection_id, item_id)


class TestAddItemToCollectionAuthorization:
    """Test authorization checks in add item to collection."""

    def test_add_item_to_collection_item_owned_by_different_user(self, boto_session):
        """Test adding item owned by different user fails."""
        service = CollectionService(
            session=boto_session,
            collections_table_name="test-collections",
            items_table_name="test-items",
        )

        # Mock the repositories
        service.collections_repo.get_item = MagicMock(
            return_value={
                "collection_id": "collection-123",
                "vault_id": "vault-123",
                "user_id": "user-123",
            }
        )

        service.items_repo.query = MagicMock(
            return_value={
                "Items": [
                    {
                        "item_id": "item-123",
                        "item_type": "MEDIA",
                        "vault_id": "vault-123",
                        "user_id": "different-user",  # Different user!
                        "upload_status": "COMPLETE",
                    }
                ],
                "Count": 1,
            }
        )

        request = AddItemToCollectionRequest(
            collection_id="collection-123",
            vault_id="vault-123",
            item_id="item-123",
        )

        with pytest.raises(ForbiddenError, match="Access denied to item"):
            service.add_item_to_collection("user-123", request)


class TestRemoveItemFromCollectionValidation:
    """Test validation in remove_item_from_collection."""

    def test_remove_item_from_collection_not_in_collection(self, boto_session):
        """Test removing item not in collection."""
        service = CollectionService(
            session=boto_session,
            collections_table_name="test-collections",
            items_table_name="test-items",
        )

        # Mock get_item to return collection first, then no association
        def mock_get_item(key):
            if "COLLECTION#" in key.get("SK", ""):
                # Return collection
                return {
                    "collection_id": "collection-123",
                    "vault_id": "vault-123",
                    "user_id": "user-123",
                }
            else:
                # Return no association
                return None

        service.collections_repo.get_item = MagicMock(side_effect=mock_get_item)

        with pytest.raises(NotFoundError, match="Item not in collection"):
            service.remove_item_from_collection(
                "user-123", "vault-123", "collection-123", "item-123"
            )


class TestGetCollectionErrorHandling:
    """Test error handling in get_collection."""

    def test_get_collection_storage_error(self, boto_session):
        """Test that storage errors are properly raised."""
        from unittest.mock import MagicMock

        service = CollectionService(
            session=boto_session,
            collections_table_name="test-collections",
            items_table_name="test-items",
        )

        # Mock get_item to raise InternalServerError
        service.collections_repo.get_item = MagicMock(
            side_effect=InternalServerError("DynamoDB error")
        )

        # Should raise InternalServerError
        with pytest.raises(InternalServerError):
            service.get_collection("user-123", "vault-123", "collection-123")
