"""
Public runtime configuration route.

The SPA boots from this instead of baking the OIDC settings into its bundle, so one
web image works in every deployment. The issuer and client id are public by design:
they appear in every authorization request.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.api.routes.base_route import BaseRoute
from src.environment.config_provider import ConfigProvider
from src.shared.logger import get_logger

logger = get_logger("config_routes")


class ConfigRoute(BaseRoute):
    """Serve the client-visible settings for this deployment."""

    def __init__(self, config: ConfigProvider):
        self.config = config

    def register(self, app: APIRouter) -> None:
        @app.get("/v1/config")
        def config():
            issuer = self.config.oidc_issuer
            client_id = self.config.oidc_client_id
            if not issuer or not client_id:
                logger.error("OIDC issuer/client id not configured")
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "NOT_CONFIGURED",
                            "message": "OIDC is not configured",
                        }
                    },
                )
            return {"oidcIssuer": issuer, "oidcClientId": client_id}
