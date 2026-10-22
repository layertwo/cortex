"""
Public health check route.

Reports the API version and whether each backing AWS dependency answers.
No authentication: this is what an uptime probe calls.
"""

from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.api.routes.base_route import BaseRoute
from src.shared.logger import get_logger

logger = get_logger("health_routes")


class HealthRoute(BaseRoute):
    """Handle the readiness probe for the API and its dependencies."""

    def __init__(self, checks: dict[str, Callable[[], object]]):
        """
        Initialize the health route.

        Args:
            checks: Dependency name -> callable that raises when the dependency is unusable
        """
        self.checks = checks

    def register(self, app: APIRouter) -> None:
        """Register the health endpoint (and its unprefixed probe alias)."""

        @app.get("/v1/health")
        @app.get("/health")
        def health(request: Request):
            dependencies: dict[str, dict[str, bool]] = {}
            for name, check in self.checks.items():
                try:
                    check()
                    dependencies[name] = {"healthy": True}
                except Exception as exc:
                    # Log the type only: exception messages can carry request data.
                    logger.warning(
                        "Dependency health check failed",
                        dependency=name,
                        error_type=type(exc).__name__,
                    )
                    dependencies[name] = {"healthy": False}

            healthy = all(dep["healthy"] for dep in dependencies.values())
            return JSONResponse(
                status_code=200 if healthy else 503,
                content={
                    "status": "healthy" if healthy else "unhealthy",
                    "version": request.app.version,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "dependencies": dependencies,
                },
            )
