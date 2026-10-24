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
from src.shared.exceptions import NotFoundError
from src.shared.generated.models import (
    CreateItemRequestContent,
    CreateItemResponseContent,
    CreateItemUploadRequestContent,
    CreateItemUploadResponseContent,
    CreateUploadPartUrlsRequestContent,
    CreateUploadPartUrlsResponseContent,
    DeleteItemResponseContent,
    DeleteItemUploadResponseContent,
    FinalizeItemUploadRequestContent,
    FinalizeItemUploadResponseContent,
    GetItemContentUrlResponseContent,
    GetItemResponseContent,
    GetItemUploadResponseContent,
    ItemData,
    ListItemsResponseContent,
    UpdateItemRequestContent,
    UpdateItemResponseContent,
)
from src.shared.logger import get_logger
from src.shared.util import _encode_binary

logger = get_logger("item_routes")


def _require_vault(
    vault_service: VaultService, user_id: str, vault_id: str, operation: str
) -> None:
    """404 unless the caller owns vault_id (deny by default; a DELETING vault reads as absent)."""
    if not vault_service.vault_exists(user_id=user_id, vault_id=vault_id):
        logger.warning(
            "Vault access denied - user does not own vault", vault_id=vault_id, operation=operation
        )
        raise NotFoundError("Vault not found")


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
        "encrypted_content": _encode_binary(item.get("encrypted_content")),
        "encrypted_metadata": _encode_binary(item["encrypted_metadata"]),
        "encrypted_tags": [_encode_binary(t) for t in tags] if tags else None,
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

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """Initialize the create item route."""
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items", response_model=CreateItemResponseContent)
        def handle(
            request: CreateItemRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create item (NOTE, TASK, EVENT with inline content).

            Stores encrypted content directly in DynamoDB for non-media items.
            All sensitive data is encrypted client-side. Vault ownership is
            verified first (deny by default); a DELETING vault reads as absent.

            Requirements: 1.4, 2.1, 2.2, 24.1, 24.2, 24.3
            """
            _require_vault(self.vault_service, user_id, request.vault_id, "create_item")

            response = self.item_service.create_item(user_id, request)

            logger.info(
                "Item created successfully",
                item_id=response.item_id,
            )

            return response


class CreateItemUploadRoute(BaseRoute):
    """Create a blob upload and hand back a presigned S3 URL."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/items/upload", response_model=CreateItemUploadResponseContent)
        def handle(
            request: CreateItemUploadRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create the pending item and its upload URL.

            For files >100MB, initiates multipart upload server-side; for smaller
            files, generates a simple presigned PUT URL. The presigned PUT is
            signed with application/octet-stream (the real MIME is encrypted).
            Vault ownership is verified first (deny by default); a DELETING
            vault reads as absent, so no row or object lands under it.

            Requirements: 1.4, 1.5, 7.1, 7.2, 24.1, 24.2
            """
            _require_vault(self.vault_service, user_id, request.vault_id, "create_item_upload")

            response = self.item_service.create_item_upload(user_id, request)

            logger.info(
                "Item upload created",
                item_id=response.item_id,
                size_bytes=request.size_bytes,
            )

            return response


class GetItemUploadRoute(BaseRoute):
    """Report whether a blob upload is pending or complete."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items/{item_id}/upload", response_model=GetItemUploadResponseContent)
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """Return the upload status; ownership is checked by the service."""
            return self.item_service.get_upload_status(user_id, item_id)


class FinalizeItemUploadRoute(BaseRoute):
    """Verify an uploaded object (assembling multipart parts) and mark it complete."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/items/{item_id}/upload/finalize",
            response_model=FinalizeItemUploadResponseContent,
        )
        def handle(
            item_id: str,
            request: FinalizeItemUploadRequestContent | None = None,
            user_id: str = Depends(get_current_user),
        ):
            """
            Finalize a blob upload.

            Verifies the object exists and flips the item from PENDING to
            COMPLETE. The body is optional: multipart uploads send uploadId +
            parts, single-PUT uploads send no body.

            Requirements: 1.4, 2.2, 2.5, 24.2
            """
            response = self.item_service.finalize_upload(
                user_id=user_id, item_id=item_id, request=request
            )

            logger.info(
                "Upload finalized successfully",
                item_id=response.item_id,
            )

            return response


class CreateUploadPartUrlsRoute(BaseRoute):
    """Mint presigned URLs for multipart upload parts."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.post(
            "/v1/items/{item_id}/upload/part-urls",
            response_model=CreateUploadPartUrlsResponseContent,
        )
        def handle(
            item_id: str,
            request: CreateUploadPartUrlsRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """Mint a batch of presigned URLs for multipart upload parts."""
            return self.item_service.create_upload_part_urls(user_id, item_id, request)


class DeleteItemUploadRoute(BaseRoute):
    """Abort a pending upload and delete the pending item."""

    def __init__(self, item_service: ItemService):
        self.item_service = item_service

    def register(self, app: APIRouter) -> None:
        @app.delete(
            "/v1/items/{item_id}/upload",
            response_model=DeleteItemUploadResponseContent,
        )
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """Abort a pending multipart upload and delete the pending item."""
            return self.item_service.delete_upload(user_id, item_id)


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
            page_size: int = Query(50, alias="pageSize", ge=1, le=100),
            next_token: str | None = Query(None, alias="nextToken"),
            sort_order: str = Query("desc", alias="sortOrder", pattern="^(asc|desc)$"),
            user_id: str = Depends(get_current_user),
        ):
            """
            List items, returning encrypted metadata only.

            The server cannot decrypt the returned data. Vault ownership is
            verified before listing (deny by default).

            Requirements: 2.3, 10.1, 10.2, 24.1, 24.2
            """
            # Verify vault ownership BEFORE listing items - deny by default
            _require_vault(self.vault_service, user_id, vault_id, "list_items")

            items, next_page_token = self.item_service.list_items(
                user_id=user_id,
                vault_id=vault_id,
                page_size=page_size,
                next_token=next_token,
                sort_order=sort_order,
            )

            item_models = [ItemData(**_item_fields(item)) for item in items]

            logger.info(
                "Listed items successfully",
                vault_id=vault_id,
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


class ContentUrlRoute(BaseRoute):
    """Handle presigned content URL generation."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/items/{item_id}/content-url", response_model=GetItemContentUrlResponseContent)
        def handle(
            item_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Get a presigned content URL for a blob item.

            Generates a time-limited presigned S3 URL. Returns an error for
            inline items.

            Requirements: 4.1, 4.3, 24.2
            """
            content_url, expires_at, _encrypted_metadata, _s3_key = (
                self.item_service.get_content_url(user_id, item_id)
            )

            logger.info(
                "Generated content URL successfully",
                item_id=item_id,
            )

            return GetItemContentUrlResponseContent(
                content_url=content_url,
                expires_at=expires_at.timestamp(),
            )
