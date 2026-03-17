"""
Service Provider for Cortex API.

This module provides dependency injection, service initialization,
and FastAPI application creation for the Cortex API.
"""

import functools
import os
from functools import cached_property

import boto3
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.routes.auth import LoginRoute, RecoverRoute, RefreshRoute
from src.api.routes.collections import (
    AddItemToCollectionRoute,
    CreateCollectionRoute,
    DeleteCollectionRoute,
    GetCollectionRoute,
    ListCollectionsRoute,
    RemoveItemFromCollectionRoute,
    UpdateCollectionRoute,
)
from src.api.routes.items import (
    CompleteUploadRoute,
    CreateItemRoute,
    DeleteItemRoute,
    DownloadItemRoute,
    GetItemRoute,
    InitiateUploadRoute,
    ListItemsRoute,
    SearchItemsRoute,
    UpdateItemRoute,
)
from src.api.routes.recovery import GenerateRecoveryCodesRoute, ValidateRecoveryCodeRoute
from src.api.routes.shares import CreateShareRoute, GetShareRoute, RevokeShareRoute
from src.api.routes.tags import SearchTagsRoute
from src.api.routes.vaults import CreateVaultRoute, GetVaultSaltRoute
from src.api.services.auth_service import AuthService
from src.api.services.collection_service import CollectionService
from src.api.services.item_service import ItemService
from src.api.services.share_service import ShareService
from src.api.services.vault_service import VaultService
from src.shared.exceptions import CortexError
from src.shared.logger import get_logger

_logger = get_logger("service_provider")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response


@functools.lru_cache(maxsize=1)
def create_service_provider() -> "ServiceProvider":  # pragma: nocover
    """Create a cached ServiceProvider singleton.

    Uses lru_cache so the same instance is reused across warm Lambda invocations.
    In tests, pass service_provider directly to bypass this.
    """
    return ServiceProvider()


def lambda_entrypoint(fn):
    """Decorator that injects a cached ServiceProvider when none is provided.

    In production, creates/reuses a cached ServiceProvider via lru_cache.
    In tests, pass service_provider directly to inject a mock.
    """

    @functools.wraps(fn)
    def wrapper(event, context, service_provider=None):
        if service_provider is None:  # pragma: nocover
            service_provider = create_service_provider()
        return fn(event, context, service_provider)

    return wrapper


class ServiceProvider:
    """
    Service provider for dependency injection and service initialization.
    """

    @cached_property
    def aws_region(self):  # pragma: nocover
        """Get AWS region from environment."""
        return os.environ.get("AWS_REGION", "us-east-1")

    @cached_property
    def session(self):  # pragma: nocover
        """Create boto3 session."""
        return boto3.Session(region_name=self.aws_region)

    @cached_property
    def vaults_table_name(self):  # pragma: nocover
        """Get vaults table name from environment."""
        return os.environ["VAULTS_TABLE_NAME"]

    @cached_property
    def items_table_name(self):  # pragma: nocover
        """Get items table name from environment."""
        return os.environ["ITEMS_TABLE_NAME"]

    @cached_property
    def collections_table_name(self):  # pragma: nocover
        """Get collections table name from environment."""
        return os.environ["COLLECTIONS_TABLE_NAME"]

    @cached_property
    def shares_table_name(self):  # pragma: nocover
        """Get shares table name from environment."""
        return os.environ["SHARES_TABLE_NAME"]

    @cached_property
    def recovery_table_name(self):  # pragma: nocover
        """Get recovery table name from environment."""
        return os.environ["RECOVERY_TABLE_NAME"]

    @cached_property
    def files_bucket_name(self):  # pragma: nocover
        """Get S3 files bucket name from environment."""
        return os.environ["FILES_BUCKET_NAME"]

    # S3 client
    @cached_property
    def s3_client(self):  # pragma: nocover
        """Create S3 client."""
        return self.session.client("s3")

    # Services
    @cached_property
    def auth_service(self) -> AuthService:
        """Create authentication service."""
        return AuthService(
            session=self.session,
            recovery_table_name=self.recovery_table_name,
            cognito_client=None,  # Cognito client would be injected here in production
            user_pool_id=os.environ.get("COGNITO_USER_POOL_ID"),
        )

    @cached_property
    def vault_service(self):
        """Create vault service."""
        return VaultService(session=self.session, vaults_table_name=self.vaults_table_name)

    @cached_property
    def item_service(self) -> ItemService:
        """Create item service."""
        return ItemService(
            session=self.session,
            items_table_name=self.items_table_name,
            s3_bucket_name=self.files_bucket_name,
        )

    @cached_property
    def collection_service(self):
        """Create collection service."""
        return CollectionService(
            session=self.session,
            collections_table_name=self.collections_table_name,
            items_table_name=self.items_table_name,
        )

    @cached_property
    def share_service(self) -> ShareService:
        """Create share service."""
        return ShareService(
            session=self.session,
            shares_table_name=self.shares_table_name,
            items_table_name=self.items_table_name,
            s3_bucket_name=self.files_bucket_name,
        )

    @cached_property
    def app(self) -> FastAPI:
        """
        Create FastAPI app with all routes, middleware, and exception handlers.

        Returns:
            Configured FastAPI application
        """
        app = FastAPI(title="Cortex API", version="1.0.0")

        # Rate limiter
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

        # Security headers
        app.add_middleware(SecurityHeadersMiddleware)

        # CORS (Lambda gets this from API Gateway; containers need it explicitly)
        cors_origins = os.environ.get("CORS_ORIGINS", "").split(",")
        cors_origins = [o.strip() for o in cors_origins if o.strip()]
        if cors_origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=cors_origins,
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_headers=["Content-Type", "Authorization"],
            )

        @app.exception_handler(CortexError)
        async def cortex_error_handler(request: Request, exc: CortexError):
            return JSONResponse(
                status_code=exc.status_code,
                content={"message": exc.message},
            )

        @app.exception_handler(Exception)
        async def unhandled_error_handler(request: Request, exc: Exception):
            _logger.exception("Unhandled exception")
            return JSONResponse(
                status_code=500,
                content={"message": "Internal server error"},
            )

        # Register routes
        router = APIRouter()
        routes = [
            LoginRoute(auth_service=self.auth_service),
            RefreshRoute(auth_service=self.auth_service),
            RecoverRoute(auth_service=self.auth_service),
            CreateVaultRoute(vault_service=self.vault_service),
            GetVaultSaltRoute(vault_service=self.vault_service),
            CreateItemRoute(item_service=self.item_service),
            InitiateUploadRoute(item_service=self.item_service),
            CompleteUploadRoute(item_service=self.item_service),
            ListItemsRoute(item_service=self.item_service, vault_service=self.vault_service),
            GetItemRoute(item_service=self.item_service, vault_service=self.vault_service),
            UpdateItemRoute(item_service=self.item_service),
            DeleteItemRoute(item_service=self.item_service, vault_service=self.vault_service),
            DownloadItemRoute(item_service=self.item_service, vault_service=self.vault_service),
            SearchItemsRoute(item_service=self.item_service),
            CreateCollectionRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            ListCollectionsRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            GetCollectionRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            UpdateCollectionRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            DeleteCollectionRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            AddItemToCollectionRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            RemoveItemFromCollectionRoute(
                collection_service=self.collection_service, vault_service=self.vault_service
            ),
            SearchTagsRoute(item_service=self.item_service, vault_service=self.vault_service),
            GenerateRecoveryCodesRoute(auth_service=self.auth_service),
            ValidateRecoveryCodeRoute(auth_service=self.auth_service),
            CreateShareRoute(share_service=self.share_service),
            GetShareRoute(share_service=self.share_service),
            RevokeShareRoute(share_service=self.share_service),
        ]
        for route in routes:
            route.register(router)
        app.include_router(router)

        @app.get("/health")
        def health():
            return {"status": "ok"}

        return app

    @cached_property
    def handler(self):
        """Create Mangum handler for AWS Lambda."""
        return Mangum(self.app, lifespan="off")
