"""
Configuration provider.

Single source of truth for deployment configuration. No other module reads
environment variables; each one is a cached property here.
"""

import os
from functools import cached_property
from typing import List


def log_level() -> str:
    """Resolve the log level before any ConfigProvider exists (shared.logger import)."""
    return os.environ.get("LOG_LEVEL", "INFO")


class ConfigProvider:
    """Lazily read and cache each configuration value."""

    @cached_property
    def aws_region(self) -> str:
        return os.environ.get("AWS_REGION", "us-east-1")

    @cached_property
    def vaults_table_name(self) -> str:
        return os.environ["VAULTS_TABLE_NAME"]

    @cached_property
    def items_table_name(self) -> str:
        return os.environ["ITEMS_TABLE_NAME"]

    @cached_property
    def collections_table_name(self) -> str:
        return os.environ["COLLECTIONS_TABLE_NAME"]

    @cached_property
    def shares_table_name(self) -> str:
        return os.environ["SHARES_TABLE_NAME"]

    @cached_property
    def files_bucket_name(self) -> str:
        return os.environ["FILES_BUCKET_NAME"]

    # Empty values make the config endpoint 503 until the deployment is configured.
    @cached_property
    def oidc_issuer(self) -> str:
        return os.environ.get("OIDC_ISSUER", "").rstrip("/")

    @cached_property
    def oidc_client_id(self) -> str:
        return os.environ.get("OIDC_CLIENT_ID", "")

    @cached_property
    def cors_origins(self) -> List[str]:
        return [
            origin.strip()
            for origin in os.environ.get("CORS_ORIGINS", "").split(",")
            if origin.strip()
        ]

    # The homelab runs the metadata store (Alternator) and blob store (Garage) with
    # different keys; AWS leaves these unset and uses the default credential chain.
    @cached_property
    def dynamodb_access_key_id(self) -> str | None:
        return os.environ.get("DYNAMODB_ACCESS_KEY_ID")

    @cached_property
    def dynamodb_secret_access_key(self) -> str | None:
        return os.environ.get("DYNAMODB_SECRET_ACCESS_KEY")

    @cached_property
    def s3_access_key_id(self) -> str | None:
        return os.environ.get("S3_ACCESS_KEY_ID")

    @cached_property
    def s3_secret_access_key(self) -> str | None:
        return os.environ.get("S3_SECRET_ACCESS_KEY")
