"""
File sharing route handlers for Cortex API.

This module implements sharing-related endpoints including share creation,
access, and revocation.

Requirements: 17.3, 17.4, 17.5, 18.2, 18.5
"""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import BadRequestError
from pydantic import ValidationError as PydanticValidationError

from src.api.routes.base_route import BaseRoute
from src.api.services.share_service import ShareService
from src.shared.auth import get_user_from_context
from src.shared.models import CreateShareRequest

logger = Logger(child=True)


class CreateShareRoute(BaseRoute):
    """Handle share creation."""

    def __init__(self, share_service: ShareService):
        """Initialize the create share route."""
        self.share_service = share_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.post("/v1/shares")
        def handle():
            """
            Create item share with metadata.

            Requirements: 17.3
            """
            # Pydantic validation
            try:
                body = app.current_event.json_body
                request = CreateShareRequest(**body)
            except PydanticValidationError as e:
                logger.warning("Request validation failed", extra={"errors": e.errors()})
                raise BadRequestError("Invalid request format")

            # Extract user identity from context
            user_id = get_user_from_context(app.current_event)

            # Create share
            response = self.share_service.create_share(user_id, request)

            logger.info(
                "Share created successfully",
                extra={
                    "user_id": user_id,
                    "share_id": response.share_id,
                    "item_id": request.item_id,
                },
            )

            return {
                "share_id": response.share_id,
                "created_at": response.created_at,
                "expires_at": response.expires_at,
            }


class GetShareRoute(BaseRoute):
    """Handle share access (anonymous)."""

    def __init__(self, share_service: ShareService):
        """Initialize the get share route."""
        self.share_service = share_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/shares/<share_id>")
        def handle(share_id: str):
            """
            Access shared item (anonymous).

            Args:
                share_id: Share identifier

            Requirements: 17.4, 18.2
            """
            # Extract client IP from request context (no auth required)
            request_context = app.current_event.get("requestContext", {})
            identity = request_context.get("identity", {})
            client_ip = identity.get("sourceIp", "unknown")

            # Access share
            response = self.share_service.get_share(share_id, client_ip)

            logger.info(
                "Share accessed successfully",
                extra={
                    "share_id": share_id,
                    "client_ip": client_ip,
                },
            )

            return {
                "share_id": response.share_id,
                "item_id": response.item_id,
                "download_url": response.download_url,
                "url_expires_at": response.url_expires_at,
                "expires_at": response.expires_at,
            }


class RevokeShareRoute(BaseRoute):
    """Handle share revocation."""

    def __init__(self, share_service: ShareService):
        """Initialize the revoke share route."""
        self.share_service = share_service

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.delete("/v1/shares/<share_id>")
        def handle(share_id: str):
            """
            Revoke share.

            Args:
                share_id: Share identifier

            Requirements: 17.5, 18.5
            """
            # Extract user identity from context
            user_id = get_user_from_context(app.current_event)

            # Revoke share
            response = self.share_service.revoke_share(user_id, share_id)

            logger.info(
                "Share revoked successfully",
                extra={
                    "user_id": user_id,
                    "share_id": share_id,
                },
            )

            return {
                "message": response.message,
                "revoked_at": response.revoked_at,
            }
