"""
Collection service layer for Cortex API.

This module implements business logic for collection operations including
CRUD operations and item-collection associations.

Requirements: 12.1, 12.2, 12.3, 12.5, 13.1, 13.2, 13.3, 13.4, 13.5
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import (
    BadRequestError,
    NotFoundError,
)

from src.shared.models import (
    AddItemToCollectionRequest,
    AddItemToCollectionResponse,
    CreateCollectionRequest,
    CreateCollectionResponse,
    UpdateCollectionRequest,
    UpdateCollectionResponse,
)
from src.shared.repository import (
    DynamoDBRepository,
    encode_pagination_token,
    parse_pagination_token,
)

logger = Logger(child=True)


class CollectionService:
    """Service layer for collection operations."""

    def __init__(
        self,
        session: boto3.Session,
        collections_table_name: str,
        items_table_name: str,
    ):
        """
        Initialize collection service.

        Args:
            session: Boto3 session
            collections_table_name: DynamoDB collections table name
            items_table_name: DynamoDB items table name
        """
        self.collections_repo = DynamoDBRepository(session, collections_table_name)
        self.items_repo = DynamoDBRepository(session, items_table_name)

    def create_collection(
        self, user_id: str, request: CreateCollectionRequest
    ) -> CreateCollectionResponse:
        """
        Create collection with encrypted metadata.

        This method stores encrypted collection metadata in DynamoDB.
        All sensitive data is encrypted client-side.

        Args:
            user_id: Authenticated user ID
            request: Create collection request

        Returns:
            Create collection response with collection ID

        Raises:
            StorageError: If DynamoDB operation fails
        """
        # Generate unique collection ID
        collection_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)

        # Build DynamoDB item
        item = {
            "PK": f"VAULT#{request.vault_id}",
            "SK": f"COLLECTION#{collection_id}",
            "collection_id": collection_id,
            "vault_id": request.vault_id,
            "user_id": user_id,
            "encrypted_metadata": request.encrypted_metadata,
            "created_at": int(now.timestamp()),
            "updated_at": int(now.timestamp()),
            "item_count": 0,
        }

        # Store collection in DynamoDB
        self.collections_repo.put_item(item)

        logger.info(
            "Created collection",
            extra={
                "user_id": user_id,
                "vault_id": request.vault_id,
                "collection_id": collection_id,
            },
        )

        return CreateCollectionResponse(
            collection_id=collection_id,
            created_at=now,
        )

    def list_collections(
        self,
        user_id: str,
        vault_id: str,
        page_size: int = 50,
        next_token: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """
        List user's collections with item counts.

        This method queries DynamoDB for user's encrypted collection metadata.
        All data returned is encrypted and cannot be decrypted by the server.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID to list collections from
            page_size: Number of collections per page (1-100)
            next_token: Pagination token from previous response

        Returns:
            Tuple of (collections list, next_token)

        Raises:
            StorageError: If DynamoDB operation fails
        """
        # Parse pagination token
        exclusive_start_key = parse_pagination_token(next_token)

        # Query collections for vault
        key_condition_expression = "PK = :pk AND begins_with(SK, :sk_prefix)"
        expression_attribute_values = {
            ":pk": f"VAULT#{vault_id}",
            ":sk_prefix": "COLLECTION#",
        }

        # Execute query
        result = self.collections_repo.query(
            key_condition_expression=key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            limit=page_size,
            exclusive_start_key=exclusive_start_key,
            scan_index_forward=False,  # Most recent first
        )

        collections = result["Items"]
        last_evaluated_key = result.get("LastEvaluatedKey")

        # Encode pagination token
        next_page_token = encode_pagination_token(last_evaluated_key)

        logger.info(
            "Listed collections",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "count": len(collections),
                "has_more": next_page_token is not None,
            },
        )

        return collections, next_page_token

    def get_collection(self, user_id: str, vault_id: str, collection_id: str) -> Optional[dict]:
        """
        Get a specific collection by ID.

        This method retrieves encrypted collection metadata from DynamoDB.
        The server cannot decrypt the data.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID
            collection_id: Collection ID

        Returns:
            Collection dictionary or None if not found

        Raises:
            AuthorizationError: If user doesn't own the collection
            StorageError: If DynamoDB operation fails
        """
        key = {
            "PK": f"VAULT#{vault_id}",
            "SK": f"COLLECTION#{collection_id}",
        }

        collection = self.collections_repo.get_item(key)

        if not collection:
            logger.info(
                "Collection not found",
                extra={"user_id": user_id, "vault_id": vault_id, "collection_id": collection_id},
            )
            return None

        # Verify user owns the collection
        if collection["user_id"] != user_id:
            logger.warning(
                "User does not own collection",
                extra={
                    "user_id": user_id,
                    "collection_id": collection_id,
                    "collection_user_id": collection["user_id"],
                },
            )
            raise NotFoundError("Collection not found")

        logger.info(
            "Retrieved collection",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "collection_id": collection_id,
            },
        )

        return collection

    def update_collection(
        self, user_id: str, request: UpdateCollectionRequest
    ) -> UpdateCollectionResponse:
        """
        Update collection metadata.

        This method updates encrypted collection metadata in DynamoDB.
        All sensitive data is encrypted client-side.

        Args:
            user_id: Authenticated user ID
            request: Update collection request

        Returns:
            Update collection response

        Raises:
            ResourceNotFoundError: If collection not found
            AuthorizationError: If user doesn't own the collection
            StorageError: If DynamoDB operation fails
        """
        # Verify collection exists and user owns it
        collection = self.get_collection(user_id, request.vault_id, request.collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        # Update collection metadata
        now = datetime.now(tz=timezone.utc)
        key = {
            "PK": f"VAULT#{request.vault_id}",
            "SK": f"COLLECTION#{request.collection_id}",
        }

        update_expression = "SET encrypted_metadata = :metadata, updated_at = :updated_at"
        expression_attribute_values = {
            ":metadata": request.encrypted_metadata,
            ":updated_at": int(now.timestamp()),
        }

        self.collections_repo.update_item(
            key=key,
            update_expression=update_expression,
            expression_attribute_values=expression_attribute_values,
        )

        logger.info(
            "Updated collection",
            extra={
                "user_id": user_id,
                "vault_id": request.vault_id,
                "collection_id": request.collection_id,
            },
        )

        return UpdateCollectionResponse(
            collection_id=request.collection_id,
            updated_at=now,
        )

    def delete_collection(self, user_id: str, vault_id: str, collection_id: str) -> None:
        """
        Delete collection while preserving items.

        This method deletes the collection metadata and all item-collection
        associations, but preserves the items themselves. Uses paginated
        queries to prevent Lambda timeouts on large collections.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID
            collection_id: Collection ID to delete

        Raises:
            ResourceNotFoundError: If collection not found
            AuthorizationError: If user doesn't own the collection
            StorageError: If deletion operation fails
        """
        # Verify collection exists and user owns it
        collection = self.get_collection(user_id, vault_id, collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        # Delete all item-collection associations using paginated batch operations
        # Process in batches to prevent Lambda timeouts on large collections
        batch_size = 25  # DynamoDB batch_write_item limit
        total_deleted = 0
        exclusive_start_key = None

        while True:
            # Query associations for this collection with pagination
            key_condition_expression = "PK = :pk"
            expression_attribute_values = {
                ":pk": f"COLLECTION#{collection_id}",
            }

            query_params = {
                "key_condition_expression": key_condition_expression,
                "expression_attribute_values": expression_attribute_values,
                "limit": 100,  # Process 100 items per query iteration
            }

            if exclusive_start_key:
                query_params["exclusive_start_key"] = exclusive_start_key

            result = self.collections_repo.query(**query_params)
            associations = result["Items"]

            # Delete associations in batches
            for i in range(0, len(associations), batch_size):
                batch = associations[i : i + batch_size]

                with self.collections_repo.table.batch_writer() as writer:
                    for association in batch:
                        writer.delete_item(
                            Key={
                                "PK": association["PK"],
                                "SK": association["SK"],
                            }
                        )
                        total_deleted += 1

            # Check if there are more items to process
            if not result.get("LastEvaluatedKey"):
                break

            exclusive_start_key = result["LastEvaluatedKey"]

        logger.info(
            "Deleted item-collection associations",
            extra={
                "user_id": user_id,
                "collection_id": collection_id,
                "count": total_deleted,
            },
        )

        # Delete collection metadata
        collection_key = {
            "PK": f"VAULT#{vault_id}",
            "SK": f"COLLECTION#{collection_id}",
        }

        self.collections_repo.delete_item(collection_key)

        logger.info(
            "Deleted collection",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "collection_id": collection_id,
            },
        )

    def add_item_to_collection(
        self, user_id: str, request: AddItemToCollectionRequest
    ) -> AddItemToCollectionResponse:
        """
        Add item to collection (many-to-many support).

        This method creates an item-collection association in DynamoDB.
        Items can belong to multiple collections simultaneously.

        Args:
            user_id: Authenticated user ID
            request: Add item to collection request

        Returns:
            Add item to collection response

        Raises:
            ResourceNotFoundError: If collection or item not found
            AuthorizationError: If user doesn't own the collection or item
            StorageError: If DynamoDB operation fails
        """
        # Verify collection exists and user owns it
        collection = self.get_collection(user_id, request.vault_id, request.collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        # Verify item exists and user owns it
        # Query by vault to find item across all types (single query with begins_with)
        key_condition_expression = "PK = :pk AND begins_with(SK, :sk_prefix)"
        expression_attribute_values = {
            ":pk": f"VAULT#{request.vault_id}",
            ":sk_prefix": "ITEM#",
        }

        # Add filter to match exact item_id
        filter_expression = "item_id = :item_id"
        expression_attribute_values[":item_id"] = request.item_id

        result = self.items_repo.query(
            key_condition_expression=key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            filter_expression=filter_expression,
            limit=1,
        )

        items = result.get("Items", [])
        if not items:
            raise NotFoundError("Item not found")

        item = items[0]

        # Verify user owns the item
        if item["user_id"] != user_id:
            logger.warning(
                "User does not own item",
                extra={
                    "user_id": user_id,
                    "item_id": request.item_id,
                    "item_user_id": item["user_id"],
                },
            )
            raise NotFoundError("Item not found")

        # Create item-collection association
        now = datetime.now(tz=timezone.utc)

        association = {
            "PK": f"COLLECTION#{request.collection_id}",
            "SK": f"ITEM#{request.item_id}",
            "collection_id": request.collection_id,
            "item_id": request.item_id,
            "item_type": item["item_type"],  # Store item type for efficient lookups
            "vault_id": request.vault_id,
            "user_id": user_id,
            "added_at": int(now.timestamp()),
            # GSI for reverse lookup (find collections by item)
            "GSI1PK": f"ITEM#{request.item_id}",
            "GSI1SK": f"COLLECTION#{request.collection_id}",
        }

        # Store association with conditional write to prevent race condition
        # Only create if association doesn't already exist
        try:
            self.collections_repo.put_item(
                association,
                condition_expression="attribute_not_exists(PK)",
            )

            # Only increment if put succeeded (new association created)
            collection_key = {
                "PK": f"VAULT#{request.vault_id}",
                "SK": f"COLLECTION#{request.collection_id}",
            }

            # Use ADD to increment atomically
            update_expression = "ADD item_count :inc"
            expression_attribute_values = {
                ":inc": 1,
            }

            self.collections_repo.update_item(
                key=collection_key,
                update_expression=update_expression,
                expression_attribute_values=expression_attribute_values,
            )
        except BadRequestError:
            # Association already exists - this is idempotent, don't increment
            logger.info(
                "Item already in collection (idempotent operation)",
                extra={
                    "user_id": user_id,
                    "vault_id": request.vault_id,
                    "collection_id": request.collection_id,
                    "item_id": request.item_id,
                },
            )
            # Return success response without incrementing count
            return AddItemToCollectionResponse(
                collection_id=request.collection_id,
                item_id=request.item_id,
                added_at=datetime.fromtimestamp(association["added_at"], tz=timezone.utc),
            )

        logger.info(
            "Added item to collection",
            extra={
                "user_id": user_id,
                "vault_id": request.vault_id,
                "collection_id": request.collection_id,
                "item_id": request.item_id,
            },
        )

        return AddItemToCollectionResponse(
            collection_id=request.collection_id,
            item_id=request.item_id,
            added_at=now,
        )

    def remove_item_from_collection(
        self, user_id: str, vault_id: str, collection_id: str, item_id: str
    ) -> None:
        """
        Remove item from collection (preserve item).

        This method deletes the item-collection association but preserves
        the item itself.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID
            collection_id: Collection ID
            item_id: Item ID to remove

        Raises:
            ResourceNotFoundError: If collection or association not found
            AuthorizationError: If user doesn't own the collection
            StorageError: If deletion operation fails
        """
        # Verify collection exists and user owns it
        collection = self.get_collection(user_id, vault_id, collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        # Check if association exists
        assoc_key = {
            "PK": f"COLLECTION#{collection_id}",
            "SK": f"ITEM#{item_id}",
        }

        association = self.collections_repo.get_item(assoc_key)

        if not association:
            raise NotFoundError("Item not in collection")

        # Delete association
        self.collections_repo.delete_item(assoc_key)

        # Decrement collection item count
        collection_key = {
            "PK": f"VAULT#{vault_id}",
            "SK": f"COLLECTION#{collection_id}",
        }

        # Use ADD with negative value to decrement atomically
        update_expression = "ADD item_count :dec"
        expression_attribute_values = {
            ":dec": -1,
        }

        self.collections_repo.update_item(
            key=collection_key,
            update_expression=update_expression,
            expression_attribute_values=expression_attribute_values,
        )

        logger.info(
            "Removed item from collection",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "collection_id": collection_id,
                "item_id": item_id,
            },
        )

    def get_items_in_collection(
        self,
        user_id: str,
        vault_id: str,
        collection_id: str,
        page_size: int = 50,
        next_token: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """
        Query items by collection ID.

        This method retrieves all items in a collection by querying
        the item-collection associations.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID
            collection_id: Collection ID
            page_size: Number of items per page (1-100)
            next_token: Pagination token from previous response

        Returns:
            Tuple of (item IDs list, next_token)

        Raises:
            ResourceNotFoundError: If collection not found
            AuthorizationError: If user doesn't own the collection
            StorageError: If DynamoDB operation fails
        """
        # Verify collection exists and user owns it
        collection = self.get_collection(user_id, vault_id, collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        # Parse pagination token
        exclusive_start_key = parse_pagination_token(next_token)

        # Query associations for this collection
        key_condition_expression = "PK = :pk"
        expression_attribute_values = {
            ":pk": f"COLLECTION#{collection_id}",
        }

        result = self.collections_repo.query(
            key_condition_expression=key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            limit=page_size,
            exclusive_start_key=exclusive_start_key,
            scan_index_forward=False,  # Most recent first
        )

        associations = result["Items"]
        last_evaluated_key = result.get("LastEvaluatedKey")

        # Encode pagination token
        next_page_token = encode_pagination_token(last_evaluated_key)

        logger.info(
            "Listed items in collection",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "collection_id": collection_id,
                "count": len(associations),
                "has_more": next_page_token is not None,
            },
        )

        return associations, next_page_token

    def get_collections_for_item(
        self,
        user_id: str,
        vault_id: str,
        item_id: str,
        page_size: int = 50,
        next_token: Optional[str] = None,
    ) -> tuple[list[dict], Optional[str]]:
        """
        Query collections by item ID (using GSI).

        This method retrieves all collections containing a specific item
        by querying the GSI on item-collection associations.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID
            item_id: Item ID
            page_size: Number of collections per page (1-100)
            next_token: Pagination token from previous response

        Returns:
            Tuple of (collection IDs list, next_token)

        Raises:
            StorageError: If DynamoDB operation fails
        """
        # Parse pagination token
        exclusive_start_key = parse_pagination_token(next_token)

        # Query GSI1 for collections containing this item
        key_condition_expression = "GSI1PK = :pk"
        expression_attribute_values = {
            ":pk": f"ITEM#{item_id}",
        }

        result = self.collections_repo.query(
            key_condition_expression=key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            index_name="GSI1",
            limit=page_size,
            exclusive_start_key=exclusive_start_key,
            scan_index_forward=False,  # Most recent first
        )

        associations = result["Items"]
        last_evaluated_key = result.get("LastEvaluatedKey")

        # Encode pagination token
        next_page_token = encode_pagination_token(last_evaluated_key)

        logger.info(
            "Listed collections for item",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "item_id": item_id,
                "count": len(associations),
                "has_more": next_page_token is not None,
            },
        )

        return associations, next_page_token
