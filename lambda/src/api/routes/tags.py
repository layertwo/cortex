"""
Tag search route handlers for Cortex API.

This module implements tag-related endpoints for searching items by encrypted tags.

Requirements: 11.4, 11.5
"""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import BadRequestError

from src.api.routes.base_route import BaseRoute
from src.api.services.item_service import ItemService
from src.api.services.vault_service import VaultService
from src.shared.auth import get_user_from_context
from src.shared.util import _encode_binary

logger = Logger(child=True)


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

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/tags/search")
        def handle():
            """
            Search by encrypted tag.

            Query parameters:
            - vault_id (required): Vault ID to search within
            - encrypted_tag (required): Base64-encoded encrypted tag to search for
            - page_size (optional): Number of results per page (default: 50, max: 100)
            - next_token (optional): Pagination token from previous response

            Returns:
                List of items with matching encrypted tag

            Requirements: 11.4, 11.5
            """
            # Extract user identity from context
            user_id = get_user_from_context(app.current_event)

            # Get query parameters
            query_params = app.current_event.query_string_parameters or {}

            vault_id = query_params.get("vault_id")
            encrypted_tag = query_params.get("encrypted_tag")
            page_size = int(query_params.get("page_size", "50"))
            next_token = query_params.get("next_token")

            # Validate required parameters
            if not vault_id:
                raise BadRequestError("Missing required parameter: vault_id")

            if not encrypted_tag:
                raise BadRequestError("Missing required parameter: encrypted_tag")

            # Validate page size
            if page_size < 1 or page_size > 100:
                raise BadRequestError("page_size must be between 1 and 100")

            # Verify vault ownership (CRITICAL - OWASP A01:2021)
            if not self.vault_service.vault_exists(user_id, vault_id):
                logger.warning(
                    "Vault access denied - user does not own vault",
                    extra={
                        "user_id": user_id,
                        "vault_id": vault_id,
                        "operation": "tag_search",
                    },
                )
                raise BadRequestError("Invalid vault_id")

            # Search by encrypted tag
            response = self.item_service.search_by_tag(
                vault_id=vault_id,
                encrypted_tag=encrypted_tag,
                page_size=page_size,
                next_token=next_token,
            )

            logger.info(
                "Tag search completed",
                extra={
                    "user_id": user_id,
                    "vault_id": vault_id,
                    "result_count": len(response.items),
                },
            )

            # Build response
            result = {
                "items": [
                    {
                        "item_id": item.item_id,
                        "item_type": item.item_type,
                        "encrypted_metadata": _encode_binary(item.encrypted_metadata),
                        "encrypted_tags": (
                            [_encode_binary(tag) for tag in item.encrypted_tags]
                            if item.encrypted_tags
                            else None
                        ),
                        "created_at": item.created_at.isoformat(),
                        "updated_at": item.updated_at.isoformat(),
                        "version": item.version,
                    }
                    for item in response.items
                ],
            }

            # Add optional fields for media items
            for i, item in enumerate(response.items):
                if hasattr(item, "s3_key") and item.s3_key:
                    result["items"][i]["s3_key"] = item.s3_key
                if hasattr(item, "size_bytes") and item.size_bytes:
                    result["items"][i]["size_bytes"] = item.size_bytes

            # Add pagination token if present
            if response.next_token:
                result["next_token"] = response.next_token

            return result
