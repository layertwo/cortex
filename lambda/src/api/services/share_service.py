"""
Share service layer for Cortex API.

This module implements business logic for share operations including
creating shares, accessing shared items, revoking shares, and rate limiting.

Requirements: 6.12
"""

import hashlib
import time
import uuid

import boto3

from src.shared.exceptions import (
    NotFoundError,
    RateLimitExceededError,
    ShareExpiredError,
    ShareRevokedError,
)
from src.shared.generated.models import (
    CreateShareRequestContent,
    CreateShareResponseContent,
    GetShareResponseContent,
    RevokeShareResponseContent,
)
from src.shared.logger import get_logger
from src.shared.repository import DynamoDBRepository, S3Repository
from src.shared.util import _encode_binary

logger = get_logger("share_service")

# Constants
PRESIGNED_URL_EXPIRATION = 900  # 15 minutes
RATE_LIMIT_MAX_ATTEMPTS_PER_IP = 5
RATE_LIMIT_MAX_ATTEMPTS_GLOBAL = 50
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour
TTL_GRACE_PERIOD = 86400  # 24 hours
TTL_REVOKED_CLEANUP = 604800  # 7 days
TTL_RATE_LIMIT_CLEANUP = 7200  # 2 hours


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

    def create_share(
        self, user_id: str, request: CreateShareRequestContent
    ) -> CreateShareResponseContent:
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

        # Set expiration if provided (cast float epoch -> int for DynamoDB)
        expires_at = int(request.expires_at) if request.expires_at is not None else None
        if expires_at is not None:
            share_item["expires_at"] = expires_at
            # Set TTL to expires_at + grace period for DynamoDB auto-cleanup
            share_item["ttl"] = expires_at + TTL_GRACE_PERIOD

        # Store share metadata
        self.shares_repo.put_item(share_item)

        logger.info(
            "Created share",
            **{
                "share_id": share_id,
                "item_id": request.item_id,
                "expires_at": request.expires_at,
            },
        )

        # ponytail: password-protected shares aren't implemented yet — always False.
        return CreateShareResponseContent(
            share_id=share_id,
            created_at=now,
            expires_at=expires_at,
            is_password_protected=False,
        )

    def get_share(self, share_id: str, client_ip: str) -> GetShareResponseContent:
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
                **{"share_id": share_id},
            )

        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:12]
        logger.info(
            "Share accessed",
            **{
                "share_id": share_id,
                "item_id": item_id,
                "client_ip_hash": ip_hash,
            },
        )

        return GetShareResponseContent(
            share_id=share_id,
            item_id=item_id,
            download_url=download_url,
            url_expires_at=url_expires_at,
            encrypted_metadata=_encode_binary(item["encrypted_metadata"]),
            expires_at=int(expires_at) if expires_at is not None else None,
            is_password_protected=False,
        )

    def revoke_share(self, user_id: str, share_id: str) -> RevokeShareResponseContent:
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
            **{
                "share_id": share_id,
            },
        )

        return RevokeShareResponseContent(
            message="Share revoked successfully",
            revoked_at=now,
        )

    def _check_rate_limit(self, share_id: str, client_ip: str) -> None:
        """
        Check rate limit for share access.

        Two limits enforced atomically via DynamoDB ADD:
        1. Per-IP: max 5 attempts per IP per share per hour
        2. Global: max 50 attempts per share per hour (across all IPs)

        Args:
            share_id: Share identifier
            client_ip: Client IP address

        Raises:
            RateLimitExceededError: If either rate limit exceeded
        """
        now = int(time.time())
        window_start = now - (now % RATE_LIMIT_WINDOW_SECONDS)
        window_ttl = window_start + RATE_LIMIT_WINDOW_SECONDS + TTL_RATE_LIMIT_CLEANUP

        # Atomic increment for per-IP rate limit
        ip_key = {"PK": f"SHARE#{share_id}", "SK": f"RATE#{client_ip}#{window_start}"}
        ip_result = self.shares_repo.update_item(
            key=ip_key,
            update_expression="ADD attempt_count :inc SET #ttl_attr = :ttl",
            expression_attribute_values={":inc": 1, ":ttl": window_ttl},
            expression_attribute_names={"#ttl_attr": "ttl"},
        )
        ip_count = int(ip_result.get("attempt_count", 1))

        if ip_count > RATE_LIMIT_MAX_ATTEMPTS_PER_IP:
            retry_after = window_start + RATE_LIMIT_WINDOW_SECONDS - now
            logger.warning(
                "Per-IP rate limit exceeded",
                **{"share_id": share_id, "attempt_count": ip_count},
            )
            raise RateLimitExceededError(
                message="Rate limit exceeded",
                retry_after=max(retry_after, 1),
            )

        # Atomic increment for global per-share rate limit
        global_key = {"PK": f"SHARE#{share_id}", "SK": f"RATE#GLOBAL#{window_start}"}
        global_result = self.shares_repo.update_item(
            key=global_key,
            update_expression="ADD attempt_count :inc SET #ttl_attr = :ttl",
            expression_attribute_values={":inc": 1, ":ttl": window_ttl},
            expression_attribute_names={"#ttl_attr": "ttl"},
        )
        global_count = int(global_result.get("attempt_count", 1))

        if global_count > RATE_LIMIT_MAX_ATTEMPTS_GLOBAL:
            retry_after = window_start + RATE_LIMIT_WINDOW_SECONDS - now
            logger.warning(
                "Global rate limit exceeded",
                **{"share_id": share_id, "attempt_count": global_count},
            )
            raise RateLimitExceededError(
                message="Rate limit exceeded",
                retry_after=max(retry_after, 1),
            )
