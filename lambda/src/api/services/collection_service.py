"""
Collection service layer for Cortex API.

This module implements business logic for collection operations including
CRUD operations and item-collection associations.

Requirements: 12.1, 12.2, 12.3, 12.5, 13.1, 13.2, 13.3, 13.4, 13.5
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import boto3
from botocore.exceptions import ClientError

from src.shared.exceptions import BadRequestError, ConflictError, NotFoundError
from src.shared.generated.models import AddItemToCollectionResponseContent
from src.shared.logger import get_logger
from src.shared.repository import (
    DynamoDBRepository,
    encode_pagination_token,
    parse_pagination_token,
)

logger = get_logger("collection_service")


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
        self,
        user_id: str,
        vault_id: str,
        encrypted_metadata: bytes,
        metadata_version: Optional[int] = None,
    ) -> dict:
        """
        Create collection with encrypted metadata.

        Stores the opaque, client-encrypted metadata plus the KEK version whose
        metadata key encrypted it, so a rotation sweep can tell rotated rows apart.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault the collection belongs to
            encrypted_metadata: Client-encrypted collection metadata
            metadata_version: KEK version that encrypted the metadata (defaults to 1)

        Returns:
            Dict with collection_id and created_at
        """
        collection_id = str(uuid.uuid4())
        now = int(datetime.now(tz=timezone.utc).timestamp())

        item = {
            "PK": f"VAULT#{vault_id}",
            "SK": f"COLLECTION#{collection_id}",
            "collection_id": collection_id,
            "vault_id": vault_id,
            "user_id": user_id,
            "encrypted_metadata": encrypted_metadata,
            "created_at": now,
            "updated_at": now,
            "item_count": 0,
            "metadata_version": 1 if metadata_version is None else metadata_version,
        }

        self.collections_repo.put_item(item)

        logger.info(
            "Created collection",
            **{"vault_id": vault_id, "collection_id": collection_id},
        )

        return {"collection_id": collection_id, "created_at": now}

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
            **{
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
                **{"vault_id": vault_id, "collection_id": collection_id},
            )
            return None

        # Verify user owns the collection
        if collection["user_id"] != user_id:
            logger.warning(
                "User does not own collection",
                **{
                    "collection_id": collection_id,
                },
            )
            raise NotFoundError("Collection not found")

        logger.info(
            "Retrieved collection",
            **{
                "vault_id": vault_id,
                "collection_id": collection_id,
            },
        )

        return collection

    def update_collection(
        self,
        user_id: str,
        vault_id: str,
        collection_id: str,
        encrypted_metadata: bytes,
        metadata_version: int | None = None,
        expected_metadata_version: int | None = None,
    ) -> dict:
        """
        Update collection metadata, optionally guarded by the stored metadata version.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID (collections are partitioned by vault)
            collection_id: Collection ID to update
            encrypted_metadata: New encrypted collection metadata
            metadata_version: KEK version that encrypted the new metadata; None leaves it as is
            expected_metadata_version: Optimistic lock on the stored version (1 when absent)

        Returns:
            Dict with collection_id and updated_at

        Raises:
            NotFoundError: If the collection is missing or not owned by the user
            ConflictError: If expected_metadata_version does not match the stored row
        """
        collection = self.get_collection(user_id, vault_id, collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        now = int(datetime.now(tz=timezone.utc).timestamp())
        key = {
            "PK": f"VAULT#{vault_id}",
            "SK": f"COLLECTION#{collection_id}",
        }

        update_expression = "SET encrypted_metadata = :metadata, updated_at = :updated_at"
        expression_attribute_values: dict[str, Any] = {
            ":metadata": encrypted_metadata,
            ":updated_at": now,
        }
        if metadata_version is not None:
            update_expression += ", metadata_version = :mv"
            expression_attribute_values[":mv"] = metadata_version

        if expected_metadata_version is None:
            self.collections_repo.update_item(
                key=key,
                update_expression=update_expression,
                expression_attribute_values=expression_attribute_values,
            )
        else:
            # Rows written before this attribute existed read as version 1.
            condition_expression = "metadata_version = :expected"
            if expected_metadata_version == 1:
                condition_expression = (
                    "attribute_not_exists(metadata_version) OR metadata_version = :expected"
                )
            expression_attribute_values[":expected"] = expected_metadata_version
            try:
                self.collections_repo.update_item_conditional(
                    key=key,
                    update_expression=update_expression,
                    condition_expression=condition_expression,
                    expression_attribute_values=expression_attribute_values,
                )
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    raise ConflictError(
                        "Collection was modified on another device; reload and retry"
                    ) from e
                raise

        logger.info(
            "Updated collection",
            **{"vault_id": vault_id, "collection_id": collection_id},
        )

        return {"collection_id": collection_id, "updated_at": now}

    def delete_collection(self, user_id: str, vault_id: str, collection_id: str) -> None:
        """
        Delete a collection the user owns, preserving its items.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID
            collection_id: Collection ID to delete

        Raises:
            NotFoundError: If the collection is missing or not owned by the user
        """
        collection = self.get_collection(user_id, vault_id, collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        self.purge_collection(vault_id, collection_id)

    def purge_collection(
        self,
        vault_id: str,
        collection_id: str,
        budget_spent: Callable[[], bool] | None = None,
    ) -> bool:
        """
        Remove a collection's membership rows, then the collection row. No ownership check.

        Paginated 25-row batch deletes keep one call bounded. When budget_spent
        is given, it is checked after each membership page's batch delete; a
        spent budget stops before the collection row is removed, so the next
        call resumes (already-deleted membership rows stay deleted). The vault
        deletion sweep calls this directly after its own ownership check.

        Args:
            vault_id: Vault ID
            collection_id: Collection ID to purge
            budget_spent: Optional zero-arg predicate checked between membership pages

        Returns:
            True once the collection row itself is deleted; False when the
            budget was spent first and the collection row was left in place.
        """
        total_deleted = 0
        exclusive_start_key = None

        while True:
            result = self.collections_repo.query(
                key_condition_expression="PK = :pk",
                expression_attribute_values={":pk": f"COLLECTION#{collection_id}"},
                limit=100,  # Process 100 items per query iteration
                exclusive_start_key=exclusive_start_key,
            )

            with self.collections_repo.table.batch_writer() as writer:
                for association in result["Items"]:
                    writer.delete_item(Key={"PK": association["PK"], "SK": association["SK"]})
                    total_deleted += 1

            exclusive_start_key = result.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break
            if budget_spent is not None and budget_spent():
                logger.info(
                    "Collection purge paused for budget",
                    **{"collection_id": collection_id, "count": total_deleted},
                )
                return False

        logger.info(
            "Deleted item-collection associations",
            **{"collection_id": collection_id, "count": total_deleted},
        )

        self.collections_repo.delete_item(
            {"PK": f"VAULT#{vault_id}", "SK": f"COLLECTION#{collection_id}"}
        )

        logger.info(
            "Deleted collection",
            **{"vault_id": vault_id, "collection_id": collection_id},
        )

        return True

    def add_item_to_collection(
        self, user_id: str, vault_id: str, collection_id: str, item_id: str
    ) -> AddItemToCollectionResponseContent:
        """
        Add item to collection (many-to-many support).

        This method creates an item-collection association in DynamoDB.
        Items can belong to multiple collections simultaneously.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID (collections are partitioned by vault)
            collection_id: Collection ID to add the item to
            item_id: Item ID to add

        Returns:
            Add item to collection response

        Raises:
            ResourceNotFoundError: If collection or item not found
            AuthorizationError: If user doesn't own the collection or item
            StorageError: If DynamoDB operation fails
        """
        # Verify collection exists and user owns it
        collection = self.get_collection(user_id, vault_id, collection_id)

        if not collection:
            raise NotFoundError("Collection not found")

        # Verify item exists and user owns it via direct lookup
        item = self.items_repo.get_item({"PK": f"ITEM#{item_id}", "SK": "METADATA"})

        if not item:
            raise NotFoundError("Item not found")

        # Verify user owns the item
        if item["user_id"] != user_id:
            logger.warning(
                "User does not own item",
                **{
                    "item_id": item_id,
                },
            )
            raise NotFoundError("Item not found")

        # Verify item belongs to the specified vault
        if item["vault_id"] != vault_id:
            raise NotFoundError("Item not found")

        # Create item-collection association
        now = datetime.now(tz=timezone.utc)

        association = {
            "PK": f"COLLECTION#{collection_id}",
            "SK": f"ITEM#{item_id}",
            "collection_id": collection_id,
            "item_id": item_id,
            "item_type": item["item_type"],  # Store item type for efficient lookups
            "vault_id": vault_id,
            "user_id": user_id,
            "added_at": int(now.timestamp()),
            # GSI for reverse lookup (find collections by item)
            "GSI1PK": f"ITEM#{item_id}",
            "GSI1SK": f"COLLECTION#{collection_id}",
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
                "PK": f"VAULT#{vault_id}",
                "SK": f"COLLECTION#{collection_id}",
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
                **{
                    "vault_id": vault_id,
                    "collection_id": collection_id,
                    "item_id": item_id,
                },
            )
            # Return success response without incrementing count
            return AddItemToCollectionResponseContent(
                message="Item added to collection",
                added_at=association["added_at"],
            )

        logger.info(
            "Added item to collection",
            **{
                "vault_id": vault_id,
                "collection_id": collection_id,
                "item_id": item_id,
            },
        )

        return AddItemToCollectionResponseContent(
            message="Item added to collection",
            added_at=int(now.timestamp()),
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
            **{
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
            **{
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
            **{
                "vault_id": vault_id,
                "item_id": item_id,
                "count": len(associations),
                "has_more": next_page_token is not None,
            },
        )

        return associations, next_page_token
