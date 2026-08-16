"""
Item management route handlers for Cortex API.

This module implements item-related endpoints for all item types
(MEDIA, NOTE, TASK, EVENT) including upload, download, listing, and deletion.

Request/response shapes are the Smithy-generated models
(src.shared.generated.models): camelCase wire, epoch timestamps, and Base64Bytes
blob fields (raw bytes Python-side, base64 on the wire). DynamoDB blobs are
base64-encoded with `_encode_binary` when building responses.

Requirements: 1.4, 1.5, 2.3, 4.1, 5.1, 7.1, 7.2, 10.1, 10.2, 24.1, 24.2
"""

import time

from fastapi import APIRouter, Depends, Query

from src.api.routes.base_route import BaseRoute
from src.api.services.item_service import ItemService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.exceptions import BadRequestError, NotFoundError
from src.shared.generated.models import (
    AbortItemUploadRequestContent,
    AbortItemUploadResponseContent,
    CompleteItemUploadRequestContent,
    CompleteItemUploadResponseContent,
    CreateItemRequestContent,
    CreateItemResponseContent,
    CreateUploadPartUrlsRequestContent,
    CreateUploadPartUrlsResponseContent,
    DeleteItemResponseContent,
    GetItemDownloadUrlResponseContent,
    GetItemResponseContent,
    InitiateItemUploadRequestContent,
    InitiateItemUploadResponseContent,
    ItemData,
    ItemType,
    ListItemsResponseContent,
    UpdateItemRequestContent,
    UpdateItemResponseContent,
)
from src.shared.logger import get_logger
from src.shared.util import _encode_binary

logger = get_logger("item_routes")


def _item_fields(item: dict) -> dict:
    """Map a DynamoDB item dict to the generated item-model kwargs.

    Blob fields are base64-encoded (Base64Bytes decodes them back to raw bytes,
    then re-encodes on the wire); timestamps become epoch floats. Shared by the
    ItemData (list) and GetItemResponseContent (single) shapes, which carry the
    same fields.
    """
    tags = item.get("encrypted_tags")
    return {
        "item_id": item["item_id"],
        "vault_id": item["vault_id"],
        "item_type": item["item_type"],
        "encrypted_content": _encode_binary(item.get("encrypted_content")),
        "encrypted_metadata": _encode_binary(item["encrypted_metadata"]),
        "encrypted_tags": [_encode_binary(t) for t in tags] if tags else None,
        "encrypted_date_bucket": _encode_binary(item.get("encrypted_date_bucket")),
        "time_bucket": item.get("time_bucket"),
        "size_bytes": int(item["size_bytes"]) if item.get("size_bytes") is not None else None,
        "s3_key": item.get("s3_key"),
        "wrapped_dek": _encode_binary(item.get("wrapped_dek")),
        "dek_version": int(item["dek_version"]) if item.get("dek_version") is not None else None,
        "created_at": float(item["created_at"]),
        "updated_at": float(item["updated_at"]),
        "version": int(item.get("version", 1)),
    }


class CreateItemRoute(BaseRoute):
    """Handle item creation (NOTE, TASK, EVENT with inline content)."""

    def __init__(self, item_service: ItemService):
        """Initialize the create item route."""
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items", response_model=CreateItemResponseContent)
        def handle(
            request: CreateItemRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create item (NOTE, TASK, EVENT with inline content).

            Stores encrypted content directly in DynamoDB for non-media items.
            All sensitive data is encrypted client-side.

            Requirements: 1.4, 2.1, 2.2, 24.1, 24.2, 24.3
            """
            response = self.item_service.create_item(user_id, request)

            logger.info(
                "Item created successfully",
                item_id=response.item_id,
                item_type=response.item_type,
            )

            return response


class InitiateUploadRoute(BaseRoute):
    """Handle upload initialization for MEDIA items."""

    def __init__(self, item_service: ItemService):
        """Initialize the upload initiation route."""
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items/upload/init", response_model=InitiateItemUploadResponseContent)
        def handle(
            request: InitiateItemUploadRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Initialize upload for MEDIA items, get presigned URL.

            For files >100MB, initiates multipart upload server-side; for smaller
            files, generates a simple presigned PUT URL. The presigned PUT is
            signed with application/octet-stream (the real MIME is encrypted).

            Requirements: 1.4, 1.5, 7.1, 7.2, 24.1, 24.2
            """
            response = self.item_service.initiate_upload(user_id, request)

            logger.info(
                "Upload initiated successfully",
                item_id=response.item_id,
                size_bytes=request.size_bytes,
            )

            return response


class CompleteUploadRoute(BaseRoute):
    """Handle upload completion for MEDIA items."""

    def __init__(self, item_service: ItemService):
        """Initialize the upload completion route."""
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/items/{item_id}/upload/complete",
            response_model=CompleteItemUploadResponseContent,
        )
        def handle(
            item_id: str,
            request: CompleteItemUploadRequestContent | None = None,
            user_id: str = Depends(get_current_user),
        ):
            """
            Mark MEDIA upload complete, store metadata.

            Verifies the upload succeeded and flips the item from PENDING to
            COMPLETE. The item id comes from the path (Smithy contract). The
            body is optional: multipart uploads send uploadId + parts, single-PUT
            uploads send no body.

            Requirements: 1.4, 2.2, 2.5, 24.2
            """
            response = self.item_service.complete_upload(
                user_id=user_id, item_id=item_id, request=request
            )

            logger.info(
                "Upload completed successfully",
                item_id=response.item_id,
            )

            return response


class CreateUploadPartUrlsRoute(BaseRoute):
    """Mint presigned URLs for multipart upload parts."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/items/{item_id}/upload/parts",
            response_model=CreateUploadPartUrlsResponseContent,
        )
        def handle(
            item_id: str,
            request: CreateUploadPartUrlsRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """Mint a batch of presigned URLs for multipart upload parts."""
            return self.item_service.create_upload_part_urls(user_id, item_id, request)


class AbortItemUploadRoute(BaseRoute):
    """Abort an in-progress multipart upload."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/items/{item_id}/upload/abort",
            response_model=AbortItemUploadResponseContent,
        )
        def handle(
            item_id: str,
            request: AbortItemUploadRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """Abort an in-progress multipart upload and delete the pending item."""
            return self.item_service.abort_upload(user_id, item_id, request)


class ListItemsRoute(BaseRoute):
    """Handle item listing with filters."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the list items route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items", response_model=ListItemsResponseContent)
        def handle(
            vault_id: str = Query(..., alias="vaultId", description="Vault ID"),
            item_type: str | None = Query(None, alias="itemType"),
            page_size: int = Query(50, alias="pageSize", ge=1, le=100),
            next_token: str | None = Query(None, alias="nextToken"),
            sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
            user_id: str = Depends(get_current_user),
        ):
            """
            List items (filter by type), returning encrypted metadata only.

            The server cannot decrypt the returned data. Vault ownership is
            verified before listing (deny by default).

            Requirements: 2.3, 10.1, 10.2, 24.1, 24.2
            """
            if item_type and item_type not in (
                ItemType.media,
                ItemType.note,
                ItemType.task,
                ItemType.event,
            ):
                raise BadRequestError("item_type must be MEDIA, NOTE, TASK, or EVENT")

            # Verify vault ownership BEFORE listing items - deny by default
            if not self.vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
                logger.warning(
                    "Vault access denied - user does not own vault",
                    vault_id=vault_id,
                    operation="list_items",
                )
                raise NotFoundError("Vault not found")

            items, next_page_token = self.item_service.list_items(
                user_id=user_id,
                vault_id=vault_id,
                item_type=item_type,
                page_size=page_size,
                next_token=next_token,
                sort_order=sort_order,
            )

            item_models = [ItemData(**_item_fields(item)) for item in items]

            logger.info(
                "Listed items successfully",
                vault_id=vault_id,
                item_type=item_type,
                count=len(item_models),
            )

            # ponytail: total_count is the page count (contract says "may be
            # approximate"); add a real COUNT query if global totals matter.
            return ListItemsResponseContent(
                items=item_models,
                next_token=next_page_token or None,
                total_count=len(item_models),
            )


class GetItemRoute(BaseRoute):
    """Handle single item retrieval."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the get item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items/{item_id}", response_model=GetItemResponseContent)
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Get encrypted item metadata. The server cannot decrypt it.

            Requirements: 2.3, 10.1, 24.1, 24.2
            """
            item = self.item_service.get_item(user_id, item_id)

            if item is None:
                raise NotFoundError(f"Item {item_id} not found")

            logger.info(
                "Retrieved item successfully",
                item_id=item_id,
                item_type=item["item_type"],
            )

            return GetItemResponseContent(**_item_fields(item))


class UpdateItemRoute(BaseRoute):
    """Handle item updates."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.put("/v1/items/{item_id}", response_model=UpdateItemResponseContent)
        def handle(
            item_id: str,
            request: UpdateItemRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Update an item's encrypted fields (tags / metadata / content).

            Authorization is by item ownership. Tag edits reconcile the tag
            search index best-effort.

            Requirements: 24.2 (edit tags on existing item — Slice 4)
            """
            response = self.item_service.update_item(user_id, item_id, request)
            logger.info(
                "Item updated successfully",
                item_id=item_id,
                version=response.version,
            )
            return response


class DeleteItemRoute(BaseRoute):
    """Handle item deletion."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the delete item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.delete("/v1/items/{item_id}", response_model=DeleteItemResponseContent)
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Delete an item and its associated resources.

            For MEDIA items, deletes both S3 object and DynamoDB metadata. For
            other items (NOTE, TASK, EVENT), deletes the DynamoDB record only.

            Requirements: 5.1, 24.2
            """
            self.item_service.delete_item(user_id, item_id)

            logger.info(
                "Item deleted successfully",
                item_id=item_id,
            )

            return DeleteItemResponseContent(
                message="Item deleted successfully",
                deleted_at=time.time(),
            )


class DownloadItemRoute(BaseRoute):
    """Handle item download URL generation."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the download item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items/{item_id}/download", response_model=GetItemDownloadUrlResponseContent)
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Get a presigned download URL (for MEDIA items).

            Generates a time-limited presigned S3 URL. Returns an error for
            non-MEDIA items.

            Requirements: 4.1, 4.3, 24.2
            """
            download_url, expires_at, _encrypted_metadata, _s3_key = (
                self.item_service.get_download_url(user_id, item_id)
            )

            logger.info(
                "Generated download URL successfully",
                item_id=item_id,
            )

            return GetItemDownloadUrlResponseContent(
                download_url=download_url,
                expires_at=expires_at.timestamp(),
            )


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
