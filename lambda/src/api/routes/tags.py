"""
Tag search route handlers for Cortex API.

This module implements tag-related endpoints for searching items by encrypted tags.

Requirements: 11.4, 11.5
"""

from fastapi import APIRouter, Depends, Query

from src.api.routes.base_route import BaseRoute
from src.api.services.item_service import ItemService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_current_user
from src.shared.exceptions import BadRequestError
from src.shared.generated.models import ItemData, SearchByTagResponseContent
from src.shared.logger import get_logger
from src.shared.util import _encode_binary

logger = get_logger("tag_routes")


def _tag_item_data(item) -> ItemData:
    """Map a tag-search ItemMetadata to the generated ItemData model.

    Blob fields are base64-encoded (Base64Bytes decodes them back); timestamps
    become epoch floats. Built via dict-splat so the Base64Bytes-as-str inputs
    don't trip static type checks (the validator decodes them at runtime).
    """
    fields = {
        "item_id": item.item_id,
        "vault_id": item.vault_id,
        "item_type": item.item_type,
        "encrypted_content": _encode_binary(item.encrypted_content),
        "encrypted_metadata": _encode_binary(item.encrypted_metadata),
        "encrypted_tags": (
            [_encode_binary(tag) for tag in item.encrypted_tags] if item.encrypted_tags else None
        ),
        "size_bytes": item.size_bytes,
        "s3_key": item.s3_key,
        "created_at": item.created_at.timestamp(),
        "updated_at": item.updated_at.timestamp(),
        "version": item.version,
    }
    return ItemData(**fields)


class SearchTagsRoute(BaseRoute):
    """Handle tag-based search."""

    def __init__(self, item_service: ItemService, vault_service: VaultService):
        """
        Initialize the search tags route.

        Args:
            item_service: Item service instance
            vault_service: Vault service instance
        """
        self.item_service = item_service
        self.vault_service = vault_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/tags/search", response_model=SearchByTagResponseContent)
        def handle(
            vault_id: str = Query(..., alias="vaultId", description="Vault ID to search within"),
            encrypted_tag: str = Query(
                ..., alias="encryptedTag", description="Base64-encoded encrypted tag"
            ),
            page_size: int = Query(50, alias="pageSize", ge=1, le=100),
            next_token: str | None = Query(None, alias="nextToken"),
            user_id: str = Depends(get_current_user),
        ):
            """
            Search by encrypted tag, returning items with matching tags.

            The server cannot decrypt the tag or the returned data; it matches
            the (deterministically) encrypted tag against stored tag index rows.

            Requirements: 11.4, 11.5
            """
            # Verify vault ownership (CRITICAL - OWASP A01:2021)
            if not self.vault_service.vault_exists(user_id, vault_id):
                logger.warning(
                    "Vault access denied - user does not own vault",
                    user_id=user_id,
                    vault_id=vault_id,
                    operation="tag_search",
                )
                raise BadRequestError("Invalid vault_id")

            response = self.item_service.search_by_tag(
                vault_id=vault_id,
                encrypted_tag=encrypted_tag,
                page_size=page_size,
                next_token=next_token,
            )

            logger.info(
                "Tag search completed",
                user_id=user_id,
                vault_id=vault_id,
                result_count=len(response.items),
            )

            items = [_tag_item_data(item) for item in response.items]

            return SearchByTagResponseContent(
                items=items,
                next_token=response.next_token or None,
                total_count=len(items),
            )
