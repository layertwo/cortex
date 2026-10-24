"""
Service Provider for Cortex API.

This module provides dependency injection, service initialization,
and FastAPI application creation for the Cortex API.
"""

import functools
from datetime import datetime, timezone
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

from src.api.routes.collections import (
    AddItemToCollectionRoute,
    CreateCollectionRoute,
    DeleteCollectionRoute,
    GetCollectionRoute,
    ListCollectionsRoute,
    RemoveItemFromCollectionRoute,
    UpdateCollectionRoute,
)
from src.api.routes.config import ConfigRoute
from src.api.routes.health import HealthRoute
from src.api.routes.items import (
    ContentUrlRoute,
    CreateItemRoute,
    CreateItemUploadRoute,
    CreateUploadPartUrlsRoute,
    DeleteItemRoute,
    DeleteItemUploadRoute,
    FinalizeItemUploadRoute,
    GetItemRoute,
    GetItemUploadRoute,
    ListItemsRoute,
    UpdateItemRoute,
)
from src.api.routes.shares import CreateShareRoute, GetShareRoute, RevokeShareRoute
from src.api.routes.tags import SearchTagsRoute
from src.api.routes.vaults import (
    CreateVaultRoute,
    DeleteVaultRoute,
    GetVaultRoute,
    GetVaultSaltRoute,
    ListVaultsRoute,
    UpdateVaultPasswordRoute,
    UpdateVaultRotationRoute,
    UpdateVaultRoute,
)
from src.api.services.collection_service import CollectionService
from src.api.services.item_service import ItemService
from src.api.services.share_service import ShareService
from src.api.services.vault_deletion_service import VaultDeletionService
from src.api.services.vault_service import VaultService
from src.environment.config_provider import ConfigProvider
from src.shared.exceptions import CortexError
from src.shared.logger import get_logger

_logger = get_logger("service_provider")


def _error_body(request: Request, code: str, message: str) -> dict:
    """Build the structured error response body with a request id and timestamp."""
    aws_event = request.scope.get("aws.event") or {}
    request_id = (aws_event.get("requestContext") or {}).get("requestId") or request.headers.get(
        "x-request-id", "unknown"
    )
    return {
        "error": {
            "code": code,
            "message": message,
            "requestId": request_id,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    }


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

    def __init__(self, config: ConfigProvider | None = None):
        self.config = config or ConfigProvider()

    @cached_property
    def boto_session(self) -> boto3.Session:  # pragma: nocover
        """Default session, using the standard AWS credential chain."""
        return boto3.Session(region_name=self.config.aws_region)

    @cached_property
    def dynamodb_session(self) -> boto3.Session:  # pragma: nocover
        """Alternator's own key when configured; the default session otherwise."""
        if self.config.dynamodb_access_key_id and self.config.dynamodb_secret_access_key:
            return boto3.Session(
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.dynamodb_access_key_id,
                aws_secret_access_key=self.config.dynamodb_secret_access_key,
            )
        return self.boto_session

    @cached_property
    def s3_session(self) -> boto3.Session:  # pragma: nocover
        """Garage's own key when configured; the default session otherwise."""
        if self.config.s3_access_key_id and self.config.s3_secret_access_key:
            return boto3.Session(
                region_name=self.config.aws_region,
                aws_access_key_id=self.config.s3_access_key_id,
                aws_secret_access_key=self.config.s3_secret_access_key,
            )
        return self.boto_session

    # S3 client
    @cached_property
    def s3_client(self):  # pragma: nocover
        """Create S3 client."""
        return self.s3_session.client("s3")

    # Services
    @cached_property
    def vault_service(self):
        """Create vault service."""
        return VaultService(
            session=self.dynamodb_session,
            vaults_table_name=self.config.vaults_table_name,
        )

    @cached_property
    def item_service(self) -> ItemService:
        """Create item service."""
        return ItemService(
            session=self.dynamodb_session,
            items_table_name=self.config.items_table_name,
            s3_bucket_name=self.config.files_bucket_name,
            s3_session=self.s3_session,
        )

    @cached_property
    def collection_service(self):
        """Create collection service."""
        return CollectionService(
            session=self.dynamodb_session,
            collections_table_name=self.config.collections_table_name,
            items_table_name=self.config.items_table_name,
        )

    @cached_property
    def share_service(self) -> ShareService:
        """Create share service."""
        return ShareService(
            session=self.dynamodb_session,
            shares_table_name=self.config.shares_table_name,
            items_table_name=self.config.items_table_name,
            s3_bucket_name=self.config.files_bucket_name,
            s3_session=self.s3_session,
        )

    @cached_property
    def vault_deletion_service(self) -> VaultDeletionService:
        """Create vault deletion service (bounded, resumable DeleteVault sweep)."""
        return VaultDeletionService(
            session=self.dynamodb_session,
            vault_service=self.vault_service,
            collection_service=self.collection_service,
            items_table_name=self.config.items_table_name,
            shares_table_name=self.config.shares_table_name,
            s3_bucket_name=self.config.files_bucket_name,
            s3_session=self.s3_session,
        )

    @cached_property
    def app(self) -> FastAPI:
        """
        Create FastAPI app with all routes, middleware, and exception handlers.

        Returns:
            Configured FastAPI application
        """
        app = FastAPI(title="Cortex API", version="1.0.0")
        app.state.config = self.config

        # Rate limiter
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

        # Security headers
        app.add_middleware(SecurityHeadersMiddleware)

        # CORS (Lambda gets this from API Gateway; containers need it explicitly)
        if self.config.cors_origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.config.cors_origins,
                allow_credentials=True,
                allow_methods=["GET", "POST", "PUT", "DELETE"],
                allow_headers=["Content-Type", "Authorization"],
            )

        @app.exception_handler(CortexError)
        async def cortex_error_handler(request: Request, exc: CortexError):
            headers = {}
            retry_after = getattr(exc, "retry_after", None)
            if retry_after is not None:
                headers["Retry-After"] = str(retry_after)
            return JSONResponse(
                status_code=exc.status_code,
                content=_error_body(request, exc.code, exc.message),
                headers=headers,
            )

        @app.exception_handler(Exception)
        async def unhandled_error_handler(request: Request, exc: Exception):
            # Log only the exception type -- not the full traceback, which can
            # embed user-supplied strings (filenames, metadata, request bodies)
            # and violate the zero-knowledge logging policy (issue #47).
            _logger.error(
                "Unhandled exception",
                error_type=type(exc).__name__,
            )
            return JSONResponse(
                status_code=500,
                content=_error_body(request, "INTERNAL_ERROR", "Internal server error"),
            )

        # Register routes
        router = APIRouter()
        routes = [
            CreateVaultRoute(vault_service=self.vault_service),
            ListVaultsRoute(vault_service=self.vault_service),
            GetVaultSaltRoute(vault_service=self.vault_service),
            GetVaultRoute(vault_service=self.vault_service),
            UpdateVaultRoute(vault_service=self.vault_service),
            UpdateVaultPasswordRoute(vault_service=self.vault_service),
            DeleteVaultRoute(vault_deletion_service=self.vault_deletion_service),
            UpdateVaultRotationRoute(vault_service=self.vault_service),
            CreateItemRoute(item_service=self.item_service, vault_service=self.vault_service),
            CreateItemUploadRoute(
                item_service=self.item_service, vault_service=self.vault_service
            ),
            GetItemUploadRoute(item_service=self.item_service),
            FinalizeItemUploadRoute(item_service=self.item_service),
            CreateUploadPartUrlsRoute(item_service=self.item_service),
            DeleteItemUploadRoute(item_service=self.item_service),
            ListItemsRoute(item_service=self.item_service, vault_service=self.vault_service),
            GetItemRoute(item_service=self.item_service, vault_service=self.vault_service),
            UpdateItemRoute(item_service=self.item_service),
            DeleteItemRoute(item_service=self.item_service, vault_service=self.vault_service),
            ContentUrlRoute(item_service=self.item_service, vault_service=self.vault_service),
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
            CreateShareRoute(share_service=self.share_service),
            GetShareRoute(share_service=self.share_service),
            RevokeShareRoute(share_service=self.share_service),
            ConfigRoute(config=self.config),
            HealthRoute(
                checks={
                    "dynamodb": lambda: self.vault_service.vaults_table.get_item(
                        Key={"PK": "HEALTH#PROBE", "SK": "HEALTH#PROBE"}
                    ),
                    "s3": lambda: self.s3_client.head_bucket(Bucket=self.config.files_bucket_name),
                }
            ),
        ]
        for route in routes:
            route.register(router)
        app.include_router(router)

        return app

    @cached_property
    def handler(self):
        """Create Mangum handler for AWS Lambda."""
        return Mangum(self.app, lifespan="off")
