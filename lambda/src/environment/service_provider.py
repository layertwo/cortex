"""
Service Provider for Cortex API.

This module provides dependency injection and service initialization
for the Cortex API Lambda functions.
"""

import os
from functools import cached_property

import boto3

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
from src.api.services.api_router import ApiRouter
from src.api.services.auth_service import AuthService
from src.api.services.collection_service import CollectionService
from src.api.services.item_service import ItemService
from src.api.services.share_service import ShareService
from src.api.services.vault_service import VaultService


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

    # API Router with all routes
    @cached_property
    def api_router(self):
        """
        Create API router with all registered routes.

        Returns:
            ApiRouter instance with all routes registered
        """
        return ApiRouter(
            routes=[
                # Auth routes (with service injection)
                LoginRoute(auth_service=self.auth_service),
                RefreshRoute(auth_service=self.auth_service),
                RecoverRoute(auth_service=self.auth_service),
                # Vault routes
                CreateVaultRoute(vault_service=self.vault_service),
                GetVaultSaltRoute(vault_service=self.vault_service),
                # Item routes
                CreateItemRoute(item_service=self.item_service),
                InitiateUploadRoute(item_service=self.item_service),
                CompleteUploadRoute(item_service=self.item_service),
                ListItemsRoute(item_service=self.item_service, vault_service=self.vault_service),
                GetItemRoute(item_service=self.item_service, vault_service=self.vault_service),
                UpdateItemRoute(),
                DeleteItemRoute(item_service=self.item_service, vault_service=self.vault_service),
                DownloadItemRoute(item_service=self.item_service, vault_service=self.vault_service),
                SearchItemsRoute(),
                # Collection routes
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
                # Tag routes
                SearchTagsRoute(item_service=self.item_service, vault_service=self.vault_service),
                # Share routes
                CreateShareRoute(share_service=self.share_service),
                GetShareRoute(share_service=self.share_service),
                RevokeShareRoute(share_service=self.share_service),
                # Recovery routes (with service injection)
                GenerateRecoveryCodesRoute(auth_service=self.auth_service),
                ValidateRecoveryCodeRoute(auth_service=self.auth_service),
            ]
        )
