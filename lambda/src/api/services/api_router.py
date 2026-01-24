"""
API Router service for Cortex API.

This module provides a router that registers all routes and handles
Lambda function invocations.
"""

from typing import Any, Dict, List

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

from src.api.routes.base_route import BaseRoute

logger = Logger()


class ApiRouter:
    """
    API Router that manages route registration and request handling.
    """

    def __init__(self, routes: List[BaseRoute]):
        """
        Initialize the API router with a list of routes.

        Args:
            routes: List of route instances to register
        """
        self.app = APIGatewayRestResolver()
        self.routes = routes
        self._register_routes()

    def _register_routes(self):
        """Register all routes with the API Gateway resolver."""
        for route in self.routes:
            route.register(self.app)

        logger.info(f"Registered {len(self.routes)} routes")

    def handle(self, event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        """
        Lambda handler that resolves requests using the registered routes.

        Args:
            event: API Gateway event dictionary
            context: Lambda context object

        Returns:
            API Gateway response dictionary
        """
        # Add request ID to logger context
        request_id = event.get("requestContext", {}).get("requestId", "unknown")
        logger.append_keys(request_id=request_id)

        # Log request metadata (never log sensitive data)
        logger.info(
            "Processing API request",
            extra={
                "http_method": event.get("httpMethod"),
                "path": event.get("path"),
                "request_id": request_id,
            },
        )

        # Resolve the request using the app resolver
        return self.app.resolve(event, context)
