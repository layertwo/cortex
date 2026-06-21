"""
File sharing route handlers for Cortex API.

This module implements sharing-related endpoints including share creation,
access, and revocation.

Requirements: 17.3, 17.4, 17.5, 18.2, 18.5
"""

import hashlib
import re

from fastapi import APIRouter, Depends, Request

from src.api.routes.base_route import BaseRoute
from src.api.services.share_service import ShareService
from src.shared.auth import get_current_user
from src.shared.exceptions import BadRequestError
from src.shared.generated.models import (
    CreateShareRequestContent,
    CreateShareResponseContent,
    GetShareResponseContent,
    RevokeShareResponseContent,
)
from src.shared.logger import get_logger

logger = get_logger("share_routes")

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


class CreateShareRoute(BaseRoute):
    """Handle share creation."""

    def __init__(self, share_service: ShareService):
        """Initialize the create share route."""
        self.share_service = share_service

    def register(self, app: APIRouter) -> None:
        @app.post("/v1/shares", response_model=CreateShareResponseContent)
        def handle(
            request: CreateShareRequestContent,
            user_id: str = Depends(get_current_user),
        ):
            """
            Create item share with metadata.

            Requirements: 17.3
            """
            response = self.share_service.create_share(user_id, request)

            logger.info(
                "Share created successfully",
                user_id=user_id,
                share_id=response.share_id,
                item_id=request.item_id,
            )

            return response


class GetShareRoute(BaseRoute):
    """Handle share access (anonymous)."""

    def __init__(self, share_service: ShareService):
        """Initialize the get share route."""
        self.share_service = share_service

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/shares/{share_id}", response_model=GetShareResponseContent)
        def handle(
            share_id: str,
            request: Request,
        ):
            """
            Access shared item (anonymous).

            Args:
                share_id: Share identifier

            Requirements: 17.4, 18.2
            """
            if not UUID_PATTERN.match(share_id):
                raise BadRequestError("Invalid share ID format")

            # Extract client IP from request context (no auth required)
            aws_event = request.scope.get("aws.event")
            if aws_event:
                request_context = aws_event.get("requestContext", {})
                identity = request_context.get("identity", {})
                client_ip = identity.get("sourceIp", "unknown")
            else:
                client_ip = request.client.host if request.client else "unknown"

            # Access share
            response = self.share_service.get_share(share_id, client_ip)

            ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12]
            logger.info(
                "Share accessed successfully",
                share_id=share_id,
                client_ip_hash=ip_hash,
            )

            return response


class RevokeShareRoute(BaseRoute):
    """Handle share revocation."""

    def __init__(self, share_service: ShareService):
        """Initialize the revoke share route."""
        self.share_service = share_service

    def register(self, app: APIRouter) -> None:
        @app.delete("/v1/shares/{share_id}", response_model=RevokeShareResponseContent)
        def handle(
            share_id: str,
            user_id: str = Depends(get_current_user),
        ):
            """
            Revoke share.

            Args:
                share_id: Share identifier

            Requirements: 17.5, 18.5
            """
            if not UUID_PATTERN.match(share_id):
                raise BadRequestError("Invalid share ID format")

            response = self.share_service.revoke_share(user_id, share_id)

            logger.info(
                "Share revoked successfully",
                user_id=user_id,
                share_id=share_id,
            )

            return response
