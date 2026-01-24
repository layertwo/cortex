"""
Tag search route handlers for Cortex API.

This module implements tag-related endpoints for searching items by encrypted tags.

Requirements: 11.4, 11.5
"""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver

from src.api.routes.base_route import BaseRoute

logger = Logger(child=True)


class SearchTagsRoute(BaseRoute):
    """Handle tag-based search."""

    def register(self, app: APIGatewayRestResolver) -> None:
        @app.get("/v1/tags/search")
        def handle():
            """
            Search by encrypted tag.

            This endpoint will be implemented in task 15.1.
            """
            logger.info("Search tags endpoint called")
            return {"message": "Search tags endpoint - to be implemented in task 15.1"}
