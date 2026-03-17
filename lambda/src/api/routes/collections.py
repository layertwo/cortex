"""
Collection management route handlers for Cortex API.

This module implements collection-related endpoints including CRUD operations
and item-collection associations.

Requirements: 12.1, 12.2, 12.3, 12.5, 13.1, 13.2, 13.3, 13.4, 13.5
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.routes.base_route import BaseRoute
from src.api.services.collection_service import CollectionService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.exceptions import NotFoundError
from src.shared.logger import get_logger
from src.shared.models import (
    AddItemToCollectionRequest,
    CreateCollectionRequest,
    UpdateCollectionRequest,
)

logger = get_logger("collection_routes")


class CreateCollectionRoute(BaseRoute):
    """Handle collection creation."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the create collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/collections")
        def handle(
            request: CreateCollectionRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create collection.

            This endpoint creates a new collection with encrypted metadata.
            All sensitive data is encrypted client-side.

            Requirements: 12.1, 13.1
            """
            # Verify vault ownership
            self.vault_service.vault_exists(user_id=user_id, vault_id=request.vault_id)

            # Create collection
            response = self.collection_service.create_collection(user_id, request)

            logger.info(
                "Collection created successfully",
                user_id=user_id,
                vault_id=request.vault_id,
                collection_id=response.collection_id,
            )

            return {
                "collection_id": response.collection_id,
                "created_at": response.created_at.isoformat(),
            }


class ListCollectionsRoute(BaseRoute):
    """Handle collection listing."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the list collections route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/collections")
        def handle(
            vault_id: str = Query(..., description="Vault ID"),
            page_size: int = Query(50, ge=1, le=100),
            next_token: Optional[str] = Query(None),
            user_id: str = Depends(get_current_user),
        ):
            """
            List collections.

            This endpoint returns encrypted metadata for all collections in a vault.
            The server cannot decrypt the returned data.

            Requirements: 12.2, 13.5
            """
            # Verify vault ownership
            self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id)

            # List collections
            collections, next_page_token = self.collection_service.list_collections(
                user_id=user_id,
                vault_id=vault_id,
                page_size=page_size,
                next_token=next_token,
            )

            # Convert collections to response format
            response_collections = []
            for collection in collections:
                response_item = {
                    "collection_id": collection["collection_id"],
                    "vault_id": collection["vault_id"],
                    "user_id": collection["user_id"],
                    "encrypted_metadata": collection["encrypted_metadata"],
                    "created_at": datetime.fromtimestamp(
                        collection["created_at"], tz=timezone.utc
                    ).isoformat(),
                    "updated_at": datetime.fromtimestamp(
                        collection["updated_at"], tz=timezone.utc
                    ).isoformat(),
                    "item_count": collection.get("item_count", 0),
                }

                response_collections.append(response_item)

            logger.info(
                "Listed collections successfully",
                user_id=user_id,
                vault_id=vault_id,
                count=len(response_collections),
            )

            response = {"collections": response_collections}
            if next_page_token:
                response["next_token"] = next_page_token

            return response


class GetCollectionRoute(BaseRoute):
    """Handle single collection retrieval."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the get collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/collections/{collection_id}")
        def handle(
            collection_id: str,
            vault_id: str = Query(..., description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Get collection details.

            This endpoint returns encrypted metadata for a specific collection.
            The server cannot decrypt the returned data.

            Args:
                collection_id: Collection identifier

            Requirements: 12.2, 13.1
            """
            # Verify vault ownership
            self.vault_service.vault_exists(user_id, vault_id)

            # Get collection
            collection = self.collection_service.get_collection(user_id, vault_id, collection_id)

            if not collection:
                logger.warning(
                    "Collection not found",
                    user_id=user_id,
                    collection_id=collection_id,
                )
                raise NotFoundError("Collection not found")

            # Convert collection to response format
            response = {
                "collection_id": collection["collection_id"],
                "vault_id": collection["vault_id"],
                "encrypted_metadata": collection["encrypted_metadata"],
                "created_at": datetime.fromtimestamp(
                    collection["created_at"], tz=timezone.utc
                ).isoformat(),
                "updated_at": datetime.fromtimestamp(
                    collection["updated_at"], tz=timezone.utc
                ).isoformat(),
                "item_count": collection.get("item_count", 0),
            }

            logger.info(
                "Retrieved collection successfully",
                user_id=user_id,
                collection_id=collection_id,
            )

            return response


class UpdateCollectionRoute(BaseRoute):
    """Handle collection updates."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the update collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.put("/v1/collections/{collection_id}")
        def handle(
            collection_id: str,
            body: UpdateCollectionRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Update collection.

            This endpoint updates encrypted collection metadata.
            All sensitive data is encrypted client-side.

            Args:
                collection_id: Collection identifier

            Requirements: 13.3
            """
            # Merge path param into request
            request = body.model_copy(update={"collection_id": collection_id})

            # Verify vault ownership
            self.vault_service.vault_exists(user_id=user_id, vault_id=request.vault_id)

            # Update collection
            response = self.collection_service.update_collection(user_id, request)

            logger.info(
                "Collection updated successfully",
                user_id=user_id,
                collection_id=collection_id,
            )

            return {
                "collection_id": response.collection_id,
                "updated_at": response.updated_at.isoformat(),
            }


class DeleteCollectionRoute(BaseRoute):
    """Handle collection deletion."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the delete collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.delete("/v1/collections/{collection_id}")
        def handle(
            collection_id: str,
            vault_id: str = Query(..., description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Delete collection.

            This endpoint deletes a collection and all its item associations,
            but preserves the items themselves.

            Args:
                collection_id: Collection identifier

            Requirements: 13.3, 13.4
            """
            # Verify vault ownership
            self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id)

            # Delete collection
            self.collection_service.delete_collection(user_id, vault_id, collection_id)

            logger.info(
                "Collection deleted successfully",
                user_id=user_id,
                vault_id=vault_id,
                collection_id=collection_id,
            )

            return {
                "message": "Collection deleted successfully",
                "collection_id": collection_id,
            }


class AddItemToCollectionRoute(BaseRoute):
    """Handle adding items to collections."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the add item to collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/collections/{collection_id}/items")
        def handle(
            collection_id: str,
            body: AddItemToCollectionRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Add item to collection.

            This endpoint creates an item-collection association.
            Items can belong to multiple collections simultaneously.
            Supports all item types (MEDIA, NOTE, TASK, EVENT).

            Args:
                collection_id: Collection identifier

            Requirements: 12.3, 12.5
            """
            # Merge path param into request
            request = body.model_copy(update={"collection_id": collection_id})

            # Verify vault ownership
            self.vault_service.vault_exists(user_id=user_id, vault_id=request.vault_id)

            # Add item to collection
            response = self.collection_service.add_item_to_collection(user_id, request)

            logger.info(
                "Item added to collection successfully",
                user_id=user_id,
                collection_id=collection_id,
                item_id=request.item_id,
            )

            return {
                "collection_id": response.collection_id,
                "item_id": response.item_id,
                "added_at": response.added_at.isoformat(),
            }


class RemoveItemFromCollectionRoute(BaseRoute):
    """Handle removing items from collections."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the remove item from collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.delete("/v1/collections/{collection_id}/items/{item_id}")
        def handle(
            collection_id: str,
            item_id: str,
            vault_id: str = Query(..., description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Remove item from collection.

            This endpoint deletes the item-collection association but
            preserves the item itself. Supports all item types (MEDIA, NOTE, TASK, EVENT).

            Args:
                collection_id: Collection identifier
                item_id: Item identifier

            Requirements: 13.2
            """
            # Verify vault ownership
            self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id)

            # Remove item from collection
            self.collection_service.remove_item_from_collection(
                user_id, vault_id, collection_id, item_id
            )

            logger.info(
                "Item removed from collection successfully",
                user_id=user_id,
                vault_id=vault_id,
                collection_id=collection_id,
                item_id=item_id,
            )

            return {
                "message": "Item removed from collection successfully",
                "collection_id": collection_id,
                "item_id": item_id,
            }
