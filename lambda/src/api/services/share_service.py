"""
Share service layer for Cortex API.

This module implements business logic for share operations including
creating shares, accessing shared items, revoking shares, and rate limiting.

Requirements: 6.12
"""

import time
import uuid
from typing import Optional

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import (
    NotFoundError,
)

from src.shared.models import (
    CreateShareRequest,
    CreateShareResponse,
    GetShareResponse,
    RevokeShareResponse,
)
from src.shared.repository import DynamoDBRepository, S3Repository

logger = Logger(child=True)

# Constants
PRESIGNED_URL_EXPIRATION = 900  # 15 minutes
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
TTL_GRACE_PERIOD = 86400  # 24 hours
TTL_REVOKED_CLEANUP = 604800  # 7 days
TTL_RATE_LIMIT_CLEANUP = 7200  # 2 hours


# ============================================================================
# Custom Error Classes
# ============================================================================


class ServiceError(Exception):
    """Base error class for share service errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ShareRevokedError(ServiceError):
    """Raised when attempting to access a revoked share."""

    def __init__(self, message: str = "Share has been revoked"):
        super().__init__(message=message, status_code=410)


class ShareExpiredError(ServiceError):
    """Raised when attempting to access an expired share."""

    def __init__(self, message: str = "Share has expired"):
        super().__init__(message=message, status_code=410)


class RateLimitExceededError(ServiceError):
    """Raised when rate limit is exceeded for share access."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 3600):
        self.retry_after = retry_after
        super().__init__(message=message, status_code=429)


class ShareService:
    """Service layer for share operations."""

    def __init__(
        self,
        session: boto3.Session,
        shares_table_name: str,
        items_table_name: str,
        s3_bucket_name: str,
    ):
        """
        Initialize share service.

        Args:
            session: Boto3 session
            shares_table_name: DynamoDB shares table name
            items_table_name: DynamoDB items table name
            s3_bucket_name: S3 bucket name for file storage
        """
        self.shares_repo = DynamoDBRepository(session, shares_table_name)
        self.items_repo = DynamoDBRepository(session, items_table_name)
        self.s3_repo = S3Repository(session, s3_bucket_name)

    def create_share(self, user_id: str, request: CreateShareRequest) -> CreateShareResponse:
        """
        Create a share for an item.

        Verifies the user owns the item, then stores share metadata
        in the shares table with an optional TTL for expiration.

        Args:
            user_id: Authenticated user ID
            request: Create share request

        Returns:
            CreateShareResponse with share ID and timestamps

        Raises:
            NotFoundError: If item not found or user doesn't own it
        """
        # Verify user owns the item
        item_key = {"PK": f"ITEM#{request.item_id}"}
        item = self.items_repo.get_item(item_key)

        if not item:
            raise NotFoundError("Item not found")

        if item["user_id"] != user_id:
            raise NotFoundError("Item not found")

        # Generate share ID and timestamp
        share_id = str(uuid.uuid4())
        now = int(time.time())

        # Build share item
        share_item = {
            "PK": f"SHARE#{share_id}",
            "SK": "METADATA",
            "share_id": share_id,
            "item_id": request.item_id,
            "vault_id": item.get("vault_id", ""),
            "user_id": user_id,
            "created_at": now,
            "is_revoked": False,
            "access_count": 0,
        }

        # Set expiration if provided
        if request.expires_at is not None:
            share_item["expires_at"] = request.expires_at
            # Set TTL to expires_at + grace period for DynamoDB auto-cleanup
            share_item["ttl"] = request.expires_at + TTL_GRACE_PERIOD

        # Store share metadata
        self.shares_repo.put_item(share_item)

        logger.info(
            "Created share",
            extra={
                "user_id": user_id,
                "share_id": share_id,
                "item_id": request.item_id,
                "expires_at": request.expires_at,
            },
        )

        return CreateShareResponse(
            share_id=share_id,
            created_at=now,
            expires_at=request.expires_at,
        )

    def get_share(self, share_id: str, client_ip: str) -> GetShareResponse:
        """
        Access a share and generate a presigned download URL.

        Checks rate limit, fetches share metadata, validates the share
        is not revoked or expired, generates a presigned S3 URL, and
        increments the access count.

        Args:
            share_id: Share identifier
            client_ip: Client IP address for rate limiting

        Returns:
            GetShareResponse with download URL and metadata

        Raises:
            RateLimitExceededError: If rate limit exceeded
            NotFoundError: If share not found
            ShareRevokedError: If share has been revoked
            ShareExpiredError: If share has expired
        """
        # Check rate limit
        self._check_rate_limit(share_id, client_ip)

        # Fetch share metadata
        share_key = {"PK": f"SHARE#{share_id}", "SK": "METADATA"}
        share = self.shares_repo.get_item(share_key)

        if not share:
            raise NotFoundError("Share not found")

        # Check if revoked
        if share.get("is_revoked"):
            raise ShareRevokedError()

        # Check if expired
        now = int(time.time())
        expires_at = share.get("expires_at")
        if expires_at is not None and int(expires_at) <= now:
            raise ShareExpiredError()

        # Fetch item to get S3 key
        item_id = share["item_id"]
        item_key = {"PK": f"ITEM#{item_id}"}
        item = self.items_repo.get_item(item_key)

        if not item:
            raise NotFoundError("Shared item no longer exists")

        # Generate presigned download URL
        s3_key = item["s3_key"]
        download_url = self.s3_repo.generate_download_url(s3_key, PRESIGNED_URL_EXPIRATION)
        url_expires_at = now + PRESIGNED_URL_EXPIRATION

        # Increment access count (best-effort)
        try:
            self.shares_repo.update_item(
                key={"PK": f"SHARE#{share_id}", "SK": "METADATA"},
                update_expression="SET access_count = access_count + :inc, last_accessed_at = :now",
                expression_attribute_values={":inc": 1, ":now": now},
            )
        except Exception:
            logger.warning(
                "Failed to update access count",
                extra={"share_id": share_id},
            )

        logger.info(
            "Share accessed",
            extra={
                "share_id": share_id,
                "item_id": item_id,
                "client_ip": client_ip,
            },
        )

        return GetShareResponse(
            share_id=share_id,
            item_id=item_id,
            download_url=download_url,
            url_expires_at=url_expires_at,
            expires_at=int(expires_at) if expires_at is not None else None,
        )

    def revoke_share(self, user_id: str, share_id: str) -> RevokeShareResponse:
        """
        Revoke a share.

        Verifies the user owns the share, then sets is_revoked=True
        and a TTL for 7-day cleanup.

        Args:
            user_id: Authenticated user ID
            share_id: Share identifier to revoke

        Returns:
            RevokeShareResponse with confirmation

        Raises:
            NotFoundError: If share not found or user doesn't own it
        """
        # Fetch share metadata
        share_key = {"PK": f"SHARE#{share_id}", "SK": "METADATA"}
        share = self.shares_repo.get_item(share_key)

        if not share:
            raise NotFoundError("Share not found")

        # Verify ownership
        if share["user_id"] != user_id:
            raise NotFoundError("Share not found")

        # Set revoked flag and TTL for cleanup
        now = int(time.time())
        self.shares_repo.update_item(
            key=share_key,
            update_expression="SET is_revoked = :revoked, #ttl = :ttl_val",
            expression_attribute_values={
                ":revoked": True,
                ":ttl_val": now + TTL_REVOKED_CLEANUP,
            },
            expression_attribute_names={"#ttl": "ttl"},
        )

        logger.info(
            "Share revoked",
            extra={
                "user_id": user_id,
                "share_id": share_id,
            },
        )

        return RevokeShareResponse(
            message="Share revoked successfully",
            revoked_at=now,
        )

    def _check_rate_limit(self, share_id: str, client_ip: str) -> None:
        """
        Check rate limit for share access per IP per share per hour.

        Uses a DynamoDB item to track access attempts. Max 5 attempts
        per hour per IP per share.

        Args:
            share_id: Share identifier
            client_ip: Client IP address

        Raises:
            RateLimitExceededError: If rate limit exceeded
        """
        now = int(time.time())
        rate_key = {"PK": f"SHARE#{share_id}", "SK": f"RATE#{client_ip}"}

        rate_item = self.shares_repo.get_item(rate_key)

        if rate_item:
            window_start = int(rate_item.get("window_start", 0))
            attempt_count = int(rate_item.get("attempt_count", 0))

            # Check if we're still within the rate limit window
            if now - window_start < RATE_LIMIT_WINDOW_SECONDS:
                if attempt_count >= RATE_LIMIT_MAX_ATTEMPTS:
                    retry_after = RATE_LIMIT_WINDOW_SECONDS - (now - window_start)
                    raise RateLimitExceededError(
                        message="Rate limit exceeded",
                        retry_after=max(retry_after, 1),
                    )

                # Increment attempt count
                self.shares_repo.update_item(
                    key=rate_key,
                    update_expression="SET attempt_count = attempt_count + :inc",
                    expression_attribute_values={":inc": 1},
                )
                return

        # Create or reset rate limit entry
        rate_limit_item = {
            "PK": f"SHARE#{share_id}",
            "SK": f"RATE#{client_ip}",
            "window_start": now,
            "attempt_count": 1,
            "ttl": now + TTL_RATE_LIMIT_CLEANUP,
        }
        self.shares_repo.put_item(rate_limit_item)
