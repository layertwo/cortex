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

    # Table names from environment
    @cached_property
    def users_table_name(self):  # pragma: nocover
        """Get users table name from environment."""
        return os.environ.get("USERS_TABLE_NAME", "cortex-dev-users")

    @cached_property
    def vaults_table_name(self):  # pragma: nocover
        """Get vaults table name from environment."""
        return os.environ.get("VAULTS_TABLE_NAME", "cortex-dev-vaults")

    @cached_property
    def items_table_name(self):  # pragma: nocover
        """Get items table name from environment."""
        return os.environ.get("ITEMS_TABLE_NAME", "cortex-dev-items")

    @cached_property
    def collections_table_name(self):  # pragma: nocover
        """Get collections table name from environment."""
        return os.environ.get("COLLECTIONS_TABLE_NAME", "cortex-dev-collections")

    @cached_property
    def shares_table_name(self):  # pragma: nocover
        """Get shares table name from environment."""
        return os.environ.get("SHARES_TABLE_NAME", "cortex-dev-shares")

    @cached_property
    def recovery_table_name(self):  # pragma: nocover
        """Get recovery table name from environment."""
        return os.environ.get("RECOVERY_TABLE_NAME", "cortex-dev-recovery")

    @cached_property
    def files_bucket_name(self):  # pragma: nocover
        """Get S3 files bucket name from environment."""
        return os.environ.get("FILES_BUCKET_NAME", "cortex-dev-files")

    # DynamoDB table resources
    @cached_property
    def users_table(self):  # pragma: nocover
        """Create DynamoDB users table resource."""
        resource = self.session.resource("dynamodb")
        return resource.Table(self.users_table_name)

    @cached_property
    def vaults_table(self):  # pragma: nocover
        """Create DynamoDB vaults table resource."""
        resource = self.session.resource("dynamodb")
        return resource.Table(self.vaults_table_name)

    @cached_property
    def items_table(self):  # pragma: nocover
        """Create DynamoDB items table resource."""
        resource = self.session.resource("dynamodb")
        return resource.Table(self.items_table_name)

    @cached_property
    def collections_table(self):  # pragma: nocover
        """Create DynamoDB collections table resource."""
        resource = self.session.resource("dynamodb")
        return resource.Table(self.collections_table_name)

    @cached_property
    def shares_table(self):  # pragma: nocover
        """Create DynamoDB shares table resource."""
        resource = self.session.resource("dynamodb")
        return resource.Table(self.shares_table_name)

    @cached_property
    def recovery_table(self):  # pragma: nocover
        """Create DynamoDB recovery table resource."""
        resource = self.session.resource("dynamodb")
        return resource.Table(self.recovery_table_name)

    # S3 client
    @cached_property
    def s3_client(self):  # pragma: nocover
        """Create S3 client."""
        return self.session.client("s3")

    # Services
    @cached_property
    def auth_service(self):
        """Create authentication service."""
        return AuthService(
            recovery_table=self.recovery_table,
            cognito_client=None,  # Cognito client would be injected here in production
            user_pool_id=os.environ.get("COGNITO_USER_POOL_ID"),
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
                CreateVaultRoute(),
                GetVaultSaltRoute(),
                # Item routes
                CreateItemRoute(),
                InitiateUploadRoute(),
                CompleteUploadRoute(),
                ListItemsRoute(),
                GetItemRoute(),
                UpdateItemRoute(),
                DeleteItemRoute(),
                DownloadItemRoute(),
                SearchItemsRoute(),
                # Collection routes
                CreateCollectionRoute(),
                ListCollectionsRoute(),
                GetCollectionRoute(),
                UpdateCollectionRoute(),
                DeleteCollectionRoute(),
                AddItemToCollectionRoute(),
                RemoveItemFromCollectionRoute(),
                # Tag routes
                SearchTagsRoute(),
                # Share routes
                CreateShareRoute(),
                GetShareRoute(),
                RevokeShareRoute(),
                # Recovery routes (with service injection)
                GenerateRecoveryCodesRoute(auth_service=self.auth_service),
                ValidateRecoveryCodeRoute(auth_service=self.auth_service),
            ]
        )
