"""
Item management route handlers for Cortex API.

This module implements item-related endpoints for all item types
(MEDIA, NOTE, TASK, EVENT) including upload, download, listing, and deletion.

Requirements: 1.4, 1.5, 2.3, 4.1, 5.1, 7.1, 7.2, 10.1, 10.2, 24.1, 24.2
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.routes.base_route import BaseRoute
from src.api.services.item_service import ItemService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.exceptions import BadRequestError, NotFoundError
from src.shared.logger import get_logger
from src.shared.models import (
    CompleteUploadRequest,
    CreateItemRequest,
    InitiateUploadRequest,
    ItemType,
)
from src.shared.util import _decode_binary

logger = get_logger("item_routes")


class CreateItemRoute(BaseRoute):
    """Handle item creation (NOTE, TASK, EVENT with inline content)."""

    def __init__(self, item_service: ItemService):
        """Initialize the create item route."""
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items")
        def handle(
            request: CreateItemRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create item (NOTE, TASK, EVENT with inline content).

            This endpoint stores encrypted content directly in DynamoDB
            for non-media items. All sensitive data is encrypted client-side.

            Requirements: 1.4, 2.1, 2.2, 24.1, 24.2, 24.3
            """
            # Create item
            response = self.item_service.create_item(user_id, request)

            logger.info(
                "Item created successfully",
                user_id=user_id,
                item_id=response.item_id,
                item_type=response.item_type,
            )

            return {
                "item_id": response.item_id,
                "item_type": response.item_type,
                "created_at": response.created_at.isoformat(),
            }


class InitiateUploadRoute(BaseRoute):
    """Handle upload initialization for MEDIA items."""

    def __init__(self, item_service: ItemService):
        """Initialize the upload initiation route."""
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items/upload/init")
        def handle(
            request: InitiateUploadRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Initialize upload for MEDIA items, get presigned URL.

            For files >100MB, initiates multipart upload. For smaller files,
            generates a simple presigned PUT URL.

            Requirements: 1.4, 1.5, 7.1, 7.2, 24.1, 24.2
            """
            # Initiate upload
            response = self.item_service.initiate_upload(user_id, request)

            logger.info(
                "Upload initiated successfully",
                user_id=user_id,
                item_id=response.item_id,
                size_bytes=request.size_bytes,
                multipart=response.upload_id is not None,
            )

            return {
                "item_id": response.item_id,
                "upload_url": response.upload_url,
                "expires_at": response.expires_at.isoformat(),
                "s3_key": response.s3_key,
                "upload_id": response.upload_id,
            }


class CompleteUploadRoute(BaseRoute):
    """Handle upload completion for MEDIA items."""

    def __init__(self, item_service: ItemService):
        """Initialize the upload completion route."""
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items/upload/complete")
        def handle(
            request: CompleteUploadRequest,
            user_id: str = Depends(get_current_user),
        ):
            """
            Mark MEDIA upload complete, store metadata.

            This endpoint verifies the upload succeeded and updates the item
            status from PENDING to COMPLETE.

            Requirements: 1.4, 2.2, 2.5, 24.2
            """
            # Complete upload
            response = self.item_service.complete_upload(user_id=user_id, request=request)

            logger.info(
                "Upload completed successfully",
                user_id=user_id,
                item_id=response.item_id,
            )

            return {
                "item_id": response.item_id,
                "uploaded_at": response.uploaded_at.isoformat(),
            }


class ListItemsRoute(BaseRoute):
    """Handle item listing with filters."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the list items route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items")
        def handle(
            vault_id: str = Query(..., description="Vault ID"),
            item_type: Optional[str] = Query(None),
            page_size: int = Query(50, ge=1, le=100),
            next_token: Optional[str] = Query(None),
            sort_order: str = Query("desc", pattern="^(asc|desc)$"),
            user_id: str = Depends(get_current_user),
        ):
            """
            List items (filter by type, tags, date buckets).

            This endpoint returns encrypted metadata for all items in a vault,
            with optional filtering by item type. The server cannot decrypt
            the returned data.

            Requirements: 2.3, 10.1, 10.2, 24.1, 24.2
            """
            # Validate item_type if provided
            if item_type and item_type not in [
                ItemType.MEDIA,
                ItemType.NOTE,
                ItemType.TASK,
                ItemType.EVENT,
            ]:
                raise BadRequestError("item_type must be MEDIA, NOTE, TASK, or EVENT")

            # Verify vault ownership BEFORE listing items - deny by default
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                logger.warning(
                    "Vault access denied - user does not own vault",
                    user_id=user_id,
                    vault_id=vault_id,
                    operation="list_items",
                )
                raise NotFoundError("Vault not found")

            # List items - vault ownership verified
            items, next_page_token = self.item_service.list_items(
                user_id=user_id,
                vault_id=vault_id,
                item_type=item_type,
                page_size=page_size,
                next_token=next_token,
                sort_order=sort_order,
            )
            response_items = []

            # Convert items to response format
            for item in items:
                response_item = {
                    "item_id": item["item_id"],
                    "item_type": item["item_type"],
                    "vault_id": item["vault_id"],
                    "user_id": item["user_id"],
                    "encrypted_metadata": _decode_binary(item["encrypted_metadata"]),
                    "created_at": datetime.fromtimestamp(
                        float(item["created_at"]), tz=timezone.utc
                    ).isoformat(),
                    "updated_at": datetime.fromtimestamp(
                        float(item["updated_at"]), tz=timezone.utc
                    ).isoformat(),
                }

                # Add optional fields
                if "encrypted_content" in item:
                    response_item["encrypted_content"] = item["encrypted_content"]
                if "encrypted_tags" in item:
                    response_item["encrypted_tags"] = item["encrypted_tags"]
                if "size_bytes" in item:
                    response_item["size_bytes"] = item["size_bytes"]
                if "s3_key" in item:
                    response_item["s3_key"] = item["s3_key"]

                response_items.append(response_item)

            logger.info(
                "Listed items successfully",
                user_id=user_id,
                vault_id=vault_id,
                item_type=item_type,
                count=len(response_items),
            )

            response = {"items": response_items}
            if next_page_token:
                response["next_token"] = next_page_token

            return response


class GetItemRoute(BaseRoute):
    """Handle single item retrieval."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the get item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items/{item_id}")
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Get item metadata.

            This endpoint returns encrypted metadata for a specific item.
            The server cannot decrypt the returned data.

            Args:
                item_id: Item identifier

            Requirements: 2.3, 10.1, 24.1, 24.2
            """
            # Get item
            item = self.item_service.get_item(user_id, item_id)

            # Convert item to response format
            response = {
                "item_id": item["item_id"],
                "item_type": item["item_type"],
                "vault_id": item["vault_id"],
                "encrypted_metadata": _decode_binary(item["encrypted_metadata"]),
                "created_at": datetime.fromtimestamp(
                    float(item["created_at"]), tz=timezone.utc
                ).isoformat(),
                "updated_at": datetime.fromtimestamp(
                    float(item["updated_at"]), tz=timezone.utc
                ).isoformat(),
            }

            # Add optional fields
            if "encrypted_content" in item:
                response["encrypted_content"] = item["encrypted_content"]
            if "encrypted_tags" in item:
                response["encrypted_tags"] = item["encrypted_tags"]
            if "size_bytes" in item:
                response["size_bytes"] = item["size_bytes"]
            if "s3_key" in item:
                response["s3_key"] = item["s3_key"]

            logger.info(
                "Retrieved item successfully",
                user_id=user_id,
                item_id=item_id,
                item_type=item["item_type"],
            )

            return response


class UpdateItemRoute(BaseRoute):
    """Handle item updates."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.put("/v1/items/{item_id}")
        def handle(item_id: str):
            """
            Update item.

            Args:
                item_id: Item identifier

            This endpoint will be implemented in task 12.1.
            """
            logger.info("Update item endpoint called", item_id=item_id)
            return {"message": "Update item endpoint - to be implemented in task 12.1"}


class DeleteItemRoute(BaseRoute):
    """Handle item deletion."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the delete item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.delete("/v1/items/{item_id}")
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Delete item.

            This endpoint deletes an item and its associated resources.
            For MEDIA items, deletes both S3 object and DynamoDB metadata.
            For other items (NOTE, TASK, EVENT), deletes DynamoDB record only.

            Args:
                item_id: Item identifier

            Requirements: 5.1, 24.2
            """
            # Delete item
            self.item_service.delete_item(user_id, item_id)

            logger.info(
                "Item deleted successfully",
                user_id=user_id,
                item_id=item_id,
            )

            return {"message": "Item deleted successfully", "item_id": item_id}


class DownloadItemRoute(BaseRoute):
    """Handle item download URL generation."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the download item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items/{item_id}/download")
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Get presigned download URL (for MEDIA items).

            This endpoint generates a time-limited presigned S3 URL for
            downloading MEDIA items. Returns an error for non-MEDIA items.

            Args:
                item_id: Item identifier

            Requirements: 4.1, 4.3, 24.2
            """
            # Get download URL
            download_url, expires_at, encrypted_metadata, s3_key = (
                self.item_service.get_download_url(user_id, item_id)
            )

            logger.info(
                "Generated download URL successfully",
                user_id=user_id,
                item_id=item_id,
            )

            return {
                "download_url": download_url,
                "expires_at": expires_at.isoformat(),
                "encrypted_metadata": _decode_binary(encrypted_metadata),
                "item_id": item_id,
                "s3_key": s3_key,
            }


class SearchItemsRoute(BaseRoute):
    """Handle item search across types."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items/search")
        def handle():
            """
            Search across types or specific type.

            This endpoint will be implemented in task 15.1.
            """
            logger.info("Search items endpoint called")
            return {"message": "Search items endpoint - to be implemented in task 15.1"}
