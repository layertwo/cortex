"""
Item management route handlers for Cortex API.

This module implements item-related endpoints for all item types
(MEDIA, NOTE, TASK, EVENT) including upload, download, listing, and deletion.

Requirements: 1.4, 1.5, 2.3, 4.1, 5.1, 7.1, 7.2, 10.1, 10.2, 24.1, 24.2
"""

from datetime import datetime, timezone

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from pydantic import ValidationError as PydanticValidationError

from src.api.routes.base_route import BaseRoute
from src.api.services.item_service import ItemService
from src.shared.auth import get_user_from_context
from src.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    StorageError,
    ValidationError,
)
from src.shared.models import (
    CompleteUploadRequest,
    CreateItemRequest,
    InitiateUploadRequest,
    ItemType,
)

logger = Logger(child=True)


class CreateItemRoute(BaseRoute):
    """Handle item creation (NOTE, TASK, EVENT with inline content)."""

    def __init__(self, item_service: ItemService):
        """Initialize the create item route."""
        self.item_service = item_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.post("/v1/items")
        def handle():
            """
            Create item (NOTE, TASK, EVENT with inline content).

            This endpoint stores encrypted content directly in DynamoDB
            for non-media items. All sensitive data is encrypted client-side.

            Requirements: 1.4, 2.1, 2.2, 24.1, 24.2, 24.3
            """
            try:
                # Extract user identity from context
                user_id = get_user_from_context(app.current_event)

                # Parse and validate request
                body = app.current_event.json_body
                request = CreateItemRequest(**body)

                # Create item
                response = self.item_service.create_item(user_id, request)

                logger.info(
                    "Item created successfully",
                    extra={
                        "user_id": user_id,
                        "item_id": response.item_id,
                        "item_type": response.item_type,
                    },
                )

                return {
                    "item_id": response.item_id,
                    "item_type": response.item_type,
                    "created_at": response.created_at.isoformat(),
                }

            except PydanticValidationError as e:
                logger.warning("Request validation failed", extra={"errors": e.errors()})
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body={
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": "Invalid request format",
                        }
                    },
                )

            except AuthenticationError as e:
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "statusCode": 401,
                    "body": {"error": {"code": "AUTHENTICATION_REQUIRED", "message": str(e)}},
                }

            except ValidationError as e:
                logger.warning("Validation failed", extra={"error": str(e)})
                return {
                    "statusCode": 400,
                    "body": {"error": {"code": "INVALID_REQUEST", "message": str(e)}},
                }

            except StorageError as e:
                logger.error("Storage error", extra={"error": str(e)})
                return {
                    "statusCode": 500,
                    "body": {"error": {"code": "STORAGE_ERROR", "message": str(e)}},
                }

            except Exception as e:
                logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {
                        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
                    },
                }


class InitiateUploadRoute(BaseRoute):
    """Handle upload initialization for MEDIA items."""

    def __init__(self, item_service: ItemService):
        """Initialize the upload initiation route."""
        self.item_service = item_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.post("/v1/items/upload/init")
        def handle():
            """
            Initialize upload for MEDIA items, get presigned URL.

            For files >100MB, initiates multipart upload. For smaller files,
            generates a simple presigned PUT URL.

            Requirements: 1.4, 1.5, 7.1, 7.2, 24.1, 24.2
            """
            try:
                # Extract user identity from context
                user_id = get_user_from_context(app.current_event)

                # Parse and validate request
                body = app.current_event.json_body
                request = InitiateUploadRequest(**body)

                # Initiate upload
                response = self.item_service.initiate_upload(user_id, request)

                logger.info(
                    "Upload initiated successfully",
                    extra={
                        "user_id": user_id,
                        "item_id": response.item_id,
                        "size_bytes": request.size_bytes,
                        "multipart": response.upload_id is not None,
                    },
                )

                return {
                    "item_id": response.item_id,
                    "upload_url": response.upload_url,
                    "expires_at": response.expires_at.isoformat(),
                    "s3_key": response.s3_key,
                    "upload_id": response.upload_id,
                }

            except PydanticValidationError as e:
                logger.warning("Request validation failed", extra={"errors": e.errors()})
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body={
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": "Invalid request format",
                        }
                    },
                )

            except AuthenticationError as e:
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "statusCode": 401,
                    "body": {"error": {"code": "AUTHENTICATION_REQUIRED", "message": str(e)}},
                }

            except ValidationError as e:
                logger.warning("Validation failed", extra={"error": str(e)})
                return {
                    "statusCode": 400,
                    "body": {"error": {"code": "INVALID_REQUEST", "message": str(e)}},
                }

            except StorageError as e:
                logger.error("Storage error", extra={"error": str(e)})
                return {
                    "statusCode": 500,
                    "body": {"error": {"code": "STORAGE_ERROR", "message": str(e)}},
                }

            except Exception as e:
                logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {
                        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
                    },
                }


class CompleteUploadRoute(BaseRoute):
    """Handle upload completion for MEDIA items."""

    def __init__(self, item_service: ItemService):
        """Initialize the upload completion route."""
        self.item_service = item_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.post("/v1/items/upload/complete")
        def handle():
            """
            Mark MEDIA upload complete, store metadata.

            This endpoint verifies the upload succeeded and updates the item
            status from PENDING to COMPLETE.

            Requirements: 1.4, 2.2, 2.5, 24.2
            """
            try:
                # Extract user identity from context
                user_id = get_user_from_context(app.current_event)

                # Parse and validate request
                body = app.current_event.json_body
                request = CompleteUploadRequest(**body)

                # Complete upload
                response = self.item_service.complete_upload(user_id, request)

                logger.info(
                    "Upload completed successfully",
                    extra={
                        "user_id": user_id,
                        "item_id": response.item_id,
                    },
                )

                return {
                    "item_id": response.item_id,
                    "uploaded_at": response.uploaded_at.isoformat(),
                }

            except PydanticValidationError as e:
                logger.warning("Request validation failed", extra={"errors": e.errors()})
                return Response(
                    status_code=400,
                    content_type="application/json",
                    body={
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": "Invalid request format",
                        }
                    },
                )

            except AuthenticationError as e:
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "statusCode": 401,
                    "body": {"error": {"code": "AUTHENTICATION_REQUIRED", "message": str(e)}},
                }

            except AuthorizationError as e:
                logger.warning("Authorization failed", extra={"error": str(e)})
                return {
                    "statusCode": 403,
                    "body": {"error": {"code": "AUTHORIZATION_FAILED", "message": str(e)}},
                }

            except ResourceNotFoundError as e:
                logger.warning("Resource not found", extra={"error": str(e)})
                return {
                    "statusCode": 404,
                    "body": {"error": {"code": "RESOURCE_NOT_FOUND", "message": str(e)}},
                }

            except ValidationError as e:
                logger.warning("Validation failed", extra={"error": str(e)})
                return {
                    "statusCode": 400,
                    "body": {"error": {"code": "INVALID_REQUEST", "message": str(e)}},
                }

            except StorageError as e:
                logger.error("Storage error", extra={"error": str(e)})
                return {
                    "statusCode": 500,
                    "body": {"error": {"code": "STORAGE_ERROR", "message": str(e)}},
                }

            except Exception as e:
                logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {
                        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
                    },
                }


class ListItemsRoute(BaseRoute):
    """Handle item listing with filters."""

    def __init__(self, item_service: ItemService):
        """Initialize the list items route."""
        self.item_service = item_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/items")
        def handle():
            """
            List items (filter by type, tags, date buckets).

            This endpoint returns encrypted metadata for all items in a vault,
            with optional filtering by item type. The server cannot decrypt
            the returned data.

            Requirements: 2.3, 10.1, 10.2, 24.1, 24.2
            """
            try:
                # Extract user identity from context
                user_id = get_user_from_context(app.current_event)

                # Get query parameters
                query_params = app.current_event.query_string_parameters or {}
                vault_id = query_params.get("vault_id")
                item_type = query_params.get("item_type")
                page_size = int(query_params.get("page_size", "50"))
                next_token = query_params.get("next_token")
                sort_order = query_params.get("sort_order", "desc")

                # Validate required parameters
                if not vault_id:
                    return Response(
                        status_code=400,
                        content_type="application/json",
                        body={
                            "error": {
                                "code": "INVALID_REQUEST",
                                "message": "vault_id is required",
                            }
                        },
                    )

                # Validate page_size
                if page_size < 1 or page_size > 100:
                    return Response(
                        status_code=400,
                        content_type="application/json",
                        body={
                            "error": {
                                "code": "INVALID_REQUEST",
                                "message": "page_size must be between 1 and 100",
                            }
                        },
                    )

                # Validate sort_order
                if sort_order not in ["asc", "desc"]:
                    return Response(
                        status_code=400,
                        content_type="application/json",
                        body={
                            "error": {
                                "code": "INVALID_REQUEST",
                                "message": "sort_order must be 'asc' or 'desc'",
                            }
                        },
                    )

                # Validate item_type if provided
                if item_type and item_type not in [
                    ItemType.MEDIA,
                    ItemType.NOTE,
                    ItemType.TASK,
                    ItemType.EVENT,
                ]:
                    return Response(
                        status_code=400,
                        content_type="application/json",
                        body={
                            "error": {
                                "code": "INVALID_REQUEST",
                                "message": "item_type must be MEDIA, NOTE, TASK, or EVENT",
                            }
                        },
                    )

                # List items
                items, next_page_token = self.item_service.list_items(
                    user_id=user_id,
                    vault_id=vault_id,
                    item_type=item_type,
                    page_size=page_size,
                    next_token=next_token,
                    sort_order=sort_order,
                )

                # Convert items to response format
                response_items = []
                for item in items:
                    response_item = {
                        "item_id": item["item_id"],
                        "item_type": item["item_type"],
                        "vault_id": item["vault_id"],
                        "user_id": item["user_id"],
                        "encrypted_metadata": item["encrypted_metadata"],
                        "created_at": datetime.fromtimestamp(
                            item["created_at"], tz=timezone.utc
                        ).isoformat(),
                        "updated_at": datetime.fromtimestamp(
                            item["updated_at"], tz=timezone.utc
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
                    extra={
                        "user_id": user_id,
                        "vault_id": vault_id,
                        "item_type": item_type,
                        "count": len(response_items),
                    },
                )

                response = {"items": response_items}
                if next_page_token:
                    response["next_token"] = next_page_token

                return response

            except AuthenticationError as e:
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "statusCode": 401,
                    "body": {"error": {"code": "AUTHENTICATION_REQUIRED", "message": str(e)}},
                }

            except StorageError as e:
                logger.error("Storage error", extra={"error": str(e)})
                return {
                    "statusCode": 500,
                    "body": {"error": {"code": "STORAGE_ERROR", "message": str(e)}},
                }

            except Exception as e:
                logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {
                        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
                    },
                }


class GetItemRoute(BaseRoute):
    """Handle single item retrieval."""

    def __init__(self, item_service: ItemService):
        """Initialize the get item route."""
        self.item_service = item_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/items/<item_id>")
        def handle(item_id: str):
            """
            Get item metadata.

            This endpoint returns encrypted metadata for a specific item.
            The server cannot decrypt the returned data.

            Args:
                item_id: Item identifier

            Requirements: 2.3, 10.1, 24.1, 24.2
            """
            try:
                # Extract user identity from context
                user_id = get_user_from_context(app.current_event)

                # Get query parameters
                query_params = app.current_event.query_string_parameters or {}
                vault_id = query_params.get("vault_id")

                # Validate required parameters
                if not vault_id:
                    return Response(
                        status_code=400,
                        content_type="application/json",
                        body={
                            "error": {
                                "code": "INVALID_REQUEST",
                                "message": "vault_id is required",
                            }
                        },
                    )

                # Get item
                item = self.item_service.get_item(user_id, vault_id, item_id)

                if not item:
                    logger.warning(
                        "Item not found",
                        extra={"user_id": user_id, "item_id": item_id},
                    )
                    return {
                        "statusCode": 404,
                        "body": {
                            "error": {"code": "RESOURCE_NOT_FOUND", "message": "Item not found"}
                        },
                    }

                # Convert item to response format
                response = {
                    "item_id": item["item_id"],
                    "item_type": item["item_type"],
                    "vault_id": item["vault_id"],
                    "encrypted_metadata": item["encrypted_metadata"],
                    "created_at": datetime.fromtimestamp(
                        item["created_at"], tz=timezone.utc
                    ).isoformat(),
                    "updated_at": datetime.fromtimestamp(
                        item["updated_at"], tz=timezone.utc
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
                    extra={
                        "user_id": user_id,
                        "item_id": item_id,
                        "item_type": item["item_type"],
                    },
                )

                return response

            except AuthenticationError as e:
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "statusCode": 401,
                    "body": {"error": {"code": "AUTHENTICATION_REQUIRED", "message": str(e)}},
                }

            except AuthorizationError as e:
                logger.warning("Authorization failed", extra={"error": str(e)})
                return {
                    "statusCode": 403,
                    "body": {"error": {"code": "AUTHORIZATION_FAILED", "message": str(e)}},
                }

            except StorageError as e:
                logger.error("Storage error", extra={"error": str(e)})
                return {
                    "statusCode": 500,
                    "body": {"error": {"code": "STORAGE_ERROR", "message": str(e)}},
                }

            except Exception as e:
                logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {
                        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
                    },
                }


class UpdateItemRoute(BaseRoute):
    """Handle item updates."""

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.put("/v1/items/<item_id>")
        def handle(item_id: str):
            """
            Update item.

            Args:
                item_id: Item identifier

            This endpoint will be implemented in task 12.1.
            """
            logger.info("Update item endpoint called", extra={"item_id": item_id})
            return {"message": "Update item endpoint - to be implemented in task 12.1"}


class DeleteItemRoute(BaseRoute):
    """Handle item deletion."""

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.delete("/v1/items/<item_id>")
        def handle(item_id: str):
            """
            Delete item.

            Args:
                item_id: Item identifier

            This endpoint will be implemented in task 13.1.
            """
            logger.info("Delete item endpoint called", extra={"item_id": item_id})
            return {"message": "Delete item endpoint - to be implemented in task 13.1"}


class DownloadItemRoute(BaseRoute):
    """Handle item download URL generation."""

    def __init__(self, item_service: ItemService):
        """Initialize the download item route."""
        self.item_service = item_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/items/<item_id>/download")
        def handle(item_id: str):
            """
            Get presigned download URL (for MEDIA items).

            This endpoint generates a time-limited presigned S3 URL for
            downloading MEDIA items. Returns an error for non-MEDIA items.

            Args:
                item_id: Item identifier

            Requirements: 4.1, 4.3, 24.2
            """
            try:
                # Extract user identity from context
                user_id = get_user_from_context(app.current_event)

                # Get query parameters
                query_params = app.current_event.query_string_parameters or {}
                vault_id = query_params.get("vault_id")

                # Validate required parameters
                if not vault_id:
                    return Response(
                        status_code=400,
                        content_type="application/json",
                        body={
                            "error": {
                                "code": "INVALID_REQUEST",
                                "message": "vault_id is required",
                            }
                        },
                    )

                # Get download URL
                download_url, expires_at, encrypted_metadata, s3_key = (
                    self.item_service.get_download_url(user_id, vault_id, item_id)
                )

                logger.info(
                    "Generated download URL successfully",
                    extra={
                        "user_id": user_id,
                        "item_id": item_id,
                        "vault_id": vault_id,
                    },
                )

                return {
                    "download_url": download_url,
                    "expires_at": expires_at.isoformat(),
                    "encrypted_metadata": encrypted_metadata,
                    "item_id": item_id,
                    "s3_key": s3_key,
                }

            except AuthenticationError as e:
                logger.warning("Authentication failed", extra={"error": str(e)})
                return {
                    "statusCode": 401,
                    "body": {"error": {"code": "AUTHENTICATION_REQUIRED", "message": str(e)}},
                }

            except AuthorizationError as e:
                logger.warning("Authorization failed", extra={"error": str(e)})
                return {
                    "statusCode": 403,
                    "body": {"error": {"code": "AUTHORIZATION_FAILED", "message": str(e)}},
                }

            except ResourceNotFoundError as e:
                logger.warning("Resource not found", extra={"error": str(e)})
                return {
                    "statusCode": 404,
                    "body": {"error": {"code": "RESOURCE_NOT_FOUND", "message": str(e)}},
                }

            except ValidationError as e:
                logger.warning("Validation failed", extra={"error": str(e)})
                return {
                    "statusCode": 400,
                    "body": {"error": {"code": "INVALID_REQUEST", "message": str(e)}},
                }

            except StorageError as e:
                logger.error("Storage error", extra={"error": str(e)})
                return {
                    "statusCode": 500,
                    "body": {"error": {"code": "STORAGE_ERROR", "message": str(e)}},
                }

            except Exception as e:
                logger.error("Unexpected error", extra={"error": str(e)}, exc_info=True)
                return {
                    "statusCode": 500,
                    "body": {
                        "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"}
                    },
                }


class SearchItemsRoute(BaseRoute):
    """Handle item search across types."""

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.post("/v1/items/search")
        def handle():
            """
            Search across types or specific type.

            This endpoint will be implemented in task 15.1.
            """
            logger.info("Search items endpoint called")
            return {"message": "Search items endpoint - to be implemented in task 15.1"}
