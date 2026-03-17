"""
Base route class for Cortex API route handlers.

This module provides an abstract base class that all route handlers inherit from,
following a consistent pattern for route registration and handling.
"""

from abc import ABC, abstractmethod

from fastapi import APIRouter


class BaseRoute(ABC):
    """Base class for all route handlers."""

    @abstractmethod
    def register(self, app: APIRouter) -> None:
        """
        Register this route with the FastAPI router.

        Args:
            app: APIRouter instance
        """
        pass  # pragma: nocover
