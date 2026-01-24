"""
Base route class for Cortex API route handlers.

This module provides an abstract base class that all route handlers inherit from,
following a consistent pattern for route registration and handling.
"""

from abc import ABC, abstractmethod

from aws_lambda_powertools.event_handler import APIGatewayRestResolver


class BaseRoute(ABC):
    """Base class for all route handlers."""

    @abstractmethod
    def register(self, app: APIGatewayRestResolver) -> None:
        """
        Register this route with the API Gateway resolver.

        Args:
            app: APIGatewayRestResolver instance
        """
        pass  # pragma: nocover
