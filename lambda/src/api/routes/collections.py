"""
Collection management route handlers for Cortex API.

This module implements collection-related endpoints including CRUD operations
and item-collection associations.

Request/response shapes are the Smithy-generated models
(src.shared.generated.models): camelCase wire, epoch timestamps, Base64Bytes
blobs. Collections are partitioned by vault, so every op takes vaultId (path
body for create, query param otherwise).

Requirements: 12.1, 12.2, 12.3, 12.5, 13.1, 13.2, 13.3, 13.4, 13.5
"""

import time

from fastapi import APIRouter, Depends, Query

from src.api.routes.base_route import BaseRoute
from src.api.services.collection_service import CollectionService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.exceptions import NotFoundError
from src.shared.generated.models import (
    AddItemToCollectionRequestContent,
    AddItemToCollectionResponseContent,
    CollectionData,
    CreateCollectionRequestContent,
    CreateCollectionResponseContent,
    DeleteCollectionResponseContent,
    GetCollectionResponseContent,
    ListCollectionsResponseContent,
    RemoveItemFromCollectionResponseContent,
    UpdateCollectionRequestContent,
    UpdateCollectionResponseContent,
)
from src.shared.logger import get_logger
from src.shared.util import _encode_binary

logger = get_logger("collection_routes")


def _collection_fields(collection: dict) -> dict:
    """Map a DynamoDB collection dict to the generated collection-model kwargs."""
    return {
        "collection_id": collection["collection_id"],
        "vault_id": collection["vault_id"],
        "encrypted_metadata": _encode_binary(collection["encrypted_metadata"]),
        "item_count": int(collection.get("item_count", 0)),
        "created_at": float(collection["created_at"]),
        "updated_at": float(collection["updated_at"]),
    }


class CreateCollectionRoute(BaseRoute):
    """Handle collection creation."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the create collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/collections", response_model=CreateCollectionResponseContent)
        def handle(
            request: CreateCollectionRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create collection with encrypted metadata.

            Requirements: 12.1, 13.1
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=request.vault_id):
                raise NotFoundError("Vault not found")

            response = self.collection_service.create_collection(user_id, request)

            logger.info(
                "Collection created successfully",
                user_id=user_id,
                vault_id=request.vault_id,
                collection_id=response.collection_id,
            )

            return response


class ListCollectionsRoute(BaseRoute):
    """Handle collection listing."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the list collections route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/collections", response_model=ListCollectionsResponseContent)
        def handle(
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            page_size: int = Query(50, alias="pageSize", ge=1, le=100),
            next_token: str | None = Query(None, alias="nextToken"),
            user_id: str = Depends(get_current_user),
        ):
            """
            List collections (encrypted metadata only).

            Requirements: 12.2, 13.5
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                raise NotFoundError("Vault not found")

            collections, next_page_token = self.collection_service.list_collections(
                user_id=user_id,
                vault_id=vault_id,
                page_size=page_size,
                next_token=next_token,
            )

            collection_models = [CollectionData(**_collection_fields(c)) for c in collections]

            logger.info(
                "Listed collections successfully",
                user_id=user_id,
                vault_id=vault_id,
                count=len(collection_models),
            )

            return ListCollectionsResponseContent(
                collections=collection_models,
                next_token=next_page_token or None,
            )


class GetCollectionRoute(BaseRoute):
    """Handle single collection retrieval."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the get collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/collections/{collection_id}", response_model=GetCollectionResponseContent)
        def handle(
            collection_id: str,
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Get collection details (encrypted metadata only).

            Requirements: 12.2, 13.1
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                raise NotFoundError("Vault not found")

            collection = self.collection_service.get_collection(user_id, vault_id, collection_id)

            if not collection:
                logger.warning(
                    "Collection not found",
                    user_id=user_id,
                    collection_id=collection_id,
                )
                raise NotFoundError("Collection not found")

            logger.info(
                "Retrieved collection successfully",
                user_id=user_id,
                collection_id=collection_id,
            )

            return GetCollectionResponseContent(**_collection_fields(collection))


class UpdateCollectionRoute(BaseRoute):
    """Handle collection updates."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the update collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.put("/v1/collections/{collection_id}", response_model=UpdateCollectionResponseContent)
        def handle(
            collection_id: str,
            body: UpdateCollectionRequestContent,
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Update encrypted collection metadata.

            Requirements: 13.3
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                raise NotFoundError("Vault not found")

            response = self.collection_service.update_collection(
                user_id=user_id,
                vault_id=vault_id,
                collection_id=collection_id,
                encrypted_metadata=body.encrypted_metadata,
            )

            logger.info(
                "Collection updated successfully",
                user_id=user_id,
                collection_id=collection_id,
            )

            return response


class DeleteCollectionRoute(BaseRoute):
    """Handle collection deletion."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the delete collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.delete(
            "/v1/collections/{collection_id}", response_model=DeleteCollectionResponseContent
        )
        def handle(
            collection_id: str,
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Delete a collection (preserves its items).

            Requirements: 13.3, 13.4
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                raise NotFoundError("Vault not found")

            self.collection_service.delete_collection(user_id, vault_id, collection_id)

            logger.info(
                "Collection deleted successfully",
                user_id=user_id,
                vault_id=vault_id,
                collection_id=collection_id,
            )

            return DeleteCollectionResponseContent(
                message="Collection deleted successfully",
                deleted_at=time.time(),
            )


class AddItemToCollectionRoute(BaseRoute):
    """Handle adding items to collections."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the add item to collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/collections/{collection_id}/items",
            response_model=AddItemToCollectionResponseContent,
        )
        def handle(
            collection_id: str,
            body: AddItemToCollectionRequestContent,
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Add an item to a collection (item may belong to many collections).

            Requirements: 12.3, 12.5
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                raise NotFoundError("Vault not found")

            response = self.collection_service.add_item_to_collection(
                user_id=user_id,
                vault_id=vault_id,
                collection_id=collection_id,
                item_id=body.item_id,
            )

            logger.info(
                "Item added to collection successfully",
                user_id=user_id,
                collection_id=collection_id,
                item_id=body.item_id,
            )

            return response


class RemoveItemFromCollectionRoute(BaseRoute):
    """Handle removing items from collections."""

    def __init__(self, collection_service: CollectionService, vault_service: VaultService):
        """Initialize the remove item from collection route."""
        self.collection_service = collection_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.delete(
            "/v1/collections/{collection_id}/items/{item_id}",
            response_model=RemoveItemFromCollectionResponseContent,
        )
        def handle(
            collection_id: str,
            item_id: str,
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Remove an item from a collection (preserves the item).

            Requirements: 13.2
            """
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                raise NotFoundError("Vault not found")

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

            return RemoveItemFromCollectionResponseContent(
                message="Item removed from collection successfully",
                removed_at=time.time(),
            )
