"""
Item service layer for Cortex API.

This module implements business logic for item operations including
upload, download, listing, and deletion for all item types (MEDIA, NOTE, TASK, EVENT).

Requirements: 1.2, 1.4, 1.5, 2.1, 2.2, 2.4, 4.5, 7.1, 7.2, 7.4, 11.3, 24.1, 24.2, 24.3
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from aws_lambda_powertools import Logger

from src.shared.errors import AuthorizationError, ResourceNotFoundError, StorageError
from src.shared.models import (
    CompleteUploadRequest,
    CompleteUploadResponse,
    CreateItemRequest,
    CreateItemResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    ItemType,
)
from src.shared.repository import DynamoDBRepository, S3Repository, build_s3_key

logger = Logger(child=True)

# Multipart upload threshold: 100MB
MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024
PRESIGNED_URL_EXPIRATION = 900  # 15 minutes


class ItemService:
    """Service layer for item operations."""

    def __init__(
        self,
        session: boto3.Session,
        items_table_name: str,
        s3_bucket_name: str,
    ):
        """
        Initialize item service.

        Args:
            session: Boto3 session
            items_table_name: DynamoDB items table name
            s3_bucket_name: S3 bucket name for media storage
        """
        self.items_repo = DynamoDBRepository(session, items_table_name)
        self.s3_repo = S3Repository(session, s3_bucket_name)

    def create_item(self, user_id: str, request: CreateItemRequest) -> CreateItemResponse:
        """
        Create item with inline encrypted content (NOTE, TASK, EVENT).

        This method stores encrypted content directly in DynamoDB for
        non-media items. All sensitive data is encrypted client-side.

        Args:
            user_id: Authenticated user ID
            request: Create item request

        Returns:
            Create item response with item ID

        Raises:
            StorageError: If DynamoDB operation fails
        """
        # Generate unique item ID
        item_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)

        # Build DynamoDB item
        item = {
            "PK": f"VAULT#{request.vault_id}",
            "SK": f"ITEM#{request.item_type}#{item_id}",
            "item_id": item_id,
            "item_type": request.item_type,
            "vault_id": request.vault_id,
            "user_id": user_id,
            "encrypted_content": request.encrypted_content,
            "encrypted_metadata": request.encrypted_metadata,
            "created_at": int(now.timestamp()),
            "updated_at": int(now.timestamp()),
            "version": 1,
        }

        # Add optional fields
        if request.encrypted_tags:
            item["encrypted_tags"] = request.encrypted_tags

        if request.encrypted_date_bucket:
            item["encrypted_date_bucket"] = request.encrypted_date_bucket

        if request.time_bucket:
            item["time_bucket"] = request.time_bucket

        # Add GSI keys for type-based queries
        item["GSI1PK"] = f"VAULT#{request.vault_id}#TYPE#{request.item_type}"
        item["GSI1SK"] = f"ITEM#{item_id}"

        # Add GSI keys for date-based queries (if applicable)
        if request.time_bucket:
            item["GSI2PK"] = (
                f"VAULT#{request.vault_id}#TYPE#{request.item_type}#DATE#{request.time_bucket}"
            )
            item["GSI2SK"] = f"ITEM#{item_id}"

        # Add GSI keys for tag-based queries (if applicable)
        if request.encrypted_tags:
            # For tag search, we'll create separate GSI entries
            # This is handled in the tag search implementation
            pass

        # Store item in DynamoDB
        self.items_repo.put_item(item)

        logger.info(
            "Created item",
            extra={
                "user_id": user_id,
                "vault_id": request.vault_id,
                "item_id": item_id,
                "item_type": request.item_type,
            },
        )

        return CreateItemResponse(
            item_id=item_id,
            item_type=request.item_type,
            created_at=now,
        )

    def initiate_upload(
        self, user_id: str, request: InitiateUploadRequest
    ) -> InitiateUploadResponse:
        """
        Initiate MEDIA item upload and generate presigned S3 URL.

        For files >100MB, initiates multipart upload. For smaller files,
        generates a simple presigned PUT URL.

        Args:
            user_id: Authenticated user ID
            request: Upload initiation request

        Returns:
            Upload response with presigned URL and item ID

        Raises:
            StorageError: If S3 or DynamoDB operation fails
        """
        # Generate unique item ID
        item_id = str(uuid.uuid4())
        now = datetime.now(tz=timezone.utc)

        # Build S3 object key
        s3_key = build_s3_key(request.vault_id, item_id)

        # Determine if multipart upload is needed
        use_multipart = request.size_bytes > MULTIPART_THRESHOLD_BYTES

        upload_id = None
        upload_url = None

        if use_multipart:
            # Initiate multipart upload
            upload_id = self.s3_repo.initiate_multipart_upload(s3_key, request.content_type)

            # Generate presigned URL for first part
            # Client will request additional part URLs as needed
            upload_url = self.s3_repo.generate_multipart_upload_url(
                s3_key, request.content_type, 1, upload_id, PRESIGNED_URL_EXPIRATION
            )

            logger.info(
                "Initiated multipart upload",
                extra={
                    "user_id": user_id,
                    "item_id": item_id,
                    "upload_id": upload_id,
                    "size_bytes": request.size_bytes,
                },
            )
        else:
            # Generate simple presigned PUT URL
            upload_url = self.s3_repo.generate_upload_url(
                s3_key, request.content_type, PRESIGNED_URL_EXPIRATION
            )

            logger.info(
                "Generated upload URL",
                extra={
                    "user_id": user_id,
                    "item_id": item_id,
                    "size_bytes": request.size_bytes,
                },
            )

        # Calculate expiration time
        expires_at = now + timedelta(seconds=PRESIGNED_URL_EXPIRATION)

        # Store item metadata in DynamoDB (pending upload completion)
        item = {
            "PK": f"VAULT#{request.vault_id}",
            "SK": f"ITEM#{ItemType.MEDIA}#{item_id}",
            "item_id": item_id,
            "item_type": ItemType.MEDIA,
            "vault_id": request.vault_id,
            "user_id": user_id,
            "s3_key": s3_key,
            "encrypted_metadata": request.encrypted_metadata,
            "created_at": int(now.timestamp()),
            "updated_at": int(now.timestamp()),
            "version": 1,
            "size_bytes": request.size_bytes,
            "upload_status": "PENDING",  # Mark as pending until completion
            "ttl": int(expires_at.timestamp()),
        }

        # Add optional fields
        if request.encrypted_tags:
            item["encrypted_tags"] = request.encrypted_tags

        # Track upload_id for multipart uploads (needed for cleanup)
        if upload_id:
            item["upload_id"] = upload_id

        # Add GSI keys for type-based queries
        item["GSI1PK"] = f"VAULT#{request.vault_id}#TYPE#{ItemType.MEDIA}"
        item["GSI1SK"] = f"ITEM#{item_id}"

        # Store metadata
        self.items_repo.put_item(item)

        return InitiateUploadResponse(
            item_id=item_id,
            upload_url=upload_url,
            expires_at=expires_at,
            s3_key=s3_key,
            upload_id=upload_id,
        )

    def complete_upload(
        self, user_id: str, request: CompleteUploadRequest
    ) -> CompleteUploadResponse:
        """
        Mark MEDIA upload as complete and finalize metadata.

        This method verifies the upload succeeded and updates the item
        status from PENDING to COMPLETE. Uses conditional updates to prevent
        TOCTOU race conditions where S3 object could be deleted between
        verification and DynamoDB update.

        Args:
            user_id: Authenticated user ID
            request: Upload completion request

        Returns:
            Upload completion response

        Raises:
            ResourceNotFoundError: If item not found
            AuthorizationError: If user doesn't own the item
            StorageError: If DynamoDB operation fails or S3 verification fails
        """
        # Retrieve item from DynamoDB
        key = {
            "PK": f"VAULT#{request.vault_id}",
            "SK": f"ITEM#{ItemType.MEDIA}#{request.item_id}",
        }

        item = self.items_repo.get_item(key)

        if not item:
            logger.warning(
                "Item not found for upload completion",
                extra={"user_id": user_id, "item_id": request.item_id},
            )
            raise ResourceNotFoundError("Item not found")

        # Verify user owns the item
        if item["user_id"] != user_id:
            logger.warning(
                "User does not own item",
                extra={
                    "user_id": user_id,
                    "item_id": request.item_id,
                    "item_user_id": item["user_id"],
                },
            )
            raise AuthorizationError("Access denied to item")

        # Verify S3 object exists and get metadata (including version if available)
        s3_key = item["s3_key"]
        s3_metadata = self.s3_repo.get_object_metadata(s3_key)

        if not s3_metadata:
            logger.error(
                "S3 object not found after upload",
                extra={"user_id": user_id, "item_id": request.item_id, "s3_key": s3_key},
            )

            # Abort multipart upload if present
            upload_id = item.get("upload_id")
            if upload_id:
                try:
                    self.s3_repo.abort_multipart_upload(s3_key, upload_id)
                    logger.info(
                        "Aborted multipart upload during cleanup",
                        extra={"item_id": request.item_id, "upload_id": upload_id},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to abort multipart upload during cleanup",
                        extra={"item_id": request.item_id, "upload_id": upload_id, "error": str(e)},
                    )

            # Clean up DynamoDB entry
            self.items_repo.delete_item(key)
            raise StorageError("Upload verification failed - object not found in S3")

        # Update item status to COMPLETE with conditional expression
        # Condition ensures item is still in PENDING state (prevents double completion)
        now = datetime.now(tz=timezone.utc)

        update_expression = "SET upload_status = :status, updated_at = :updated_at"
        expression_attribute_values = {
            ":status": "COMPLETE",
            ":updated_at": int(now.timestamp()),
            ":pending": "PENDING",
        }
        expression_attribute_names = {}

        # Store S3 version ID if available (for versioned buckets)
        if s3_metadata.get("version_id"):
            update_expression += ", s3_version_id = :version_id"
            expression_attribute_values[":version_id"] = s3_metadata["version_id"]

        # Remove TTL
        update_expression += " REMOVE #ttl"
        expression_attribute_names["#ttl"] = "ttl"

        try:
            self.items_repo.update_item_conditional(
                key=key,
                update_expression=update_expression,
                condition_expression="upload_status = :pending",
                expression_attribute_values=expression_attribute_values,
                expression_attribute_names=expression_attribute_names,
            )
        except StorageError:
            # Conditional update failed - verify S3 object still exists
            if not self.s3_repo.object_exists(s3_key):
                logger.error(
                    "S3 object deleted during upload completion (TOCTOU race condition detected)",
                    extra={
                        "user_id": user_id,
                        "item_id": request.item_id,
                        "s3_key": s3_key,
                    },
                )
                # Clean up orphaned metadata
                self.items_repo.delete_item(key)
                raise StorageError(
                    "Upload verification failed - object was deleted during completion"
                )

            # Item may have already been completed or is in invalid state
            logger.warning(
                "Conditional update failed during upload completion",
                extra={
                    "user_id": user_id,
                    "item_id": request.item_id,
                    "current_status": item.get("upload_status"),
                },
            )
            raise

        logger.info(
            "Completed upload",
            extra={
                "user_id": user_id,
                "vault_id": request.vault_id,
                "item_id": request.item_id,
                "s3_version_id": s3_metadata.get("version_id"),
            },
        )

        return CompleteUploadResponse(item_id=request.item_id, uploaded_at=now.timestamp())

    def cleanup_failed_upload(
        self, vault_id: str, item_id: str, s3_key: Optional[str], upload_id: Optional[str] = None
    ) -> None:
        """
        Clean up resources after failed upload.

        This method ensures referential integrity by removing both
        S3 objects and DynamoDB metadata when uploads fail. For multipart
        uploads, it aborts the upload to prevent storage costs.

        Args:
            vault_id: Vault ID
            item_id: Item ID
            s3_key: S3 object key (if exists)
            upload_id: Multipart upload ID (if multipart upload)
        """
        try:
            # Abort multipart upload if present
            if s3_key and upload_id:
                try:
                    self.s3_repo.abort_multipart_upload(s3_key, upload_id)
                    logger.info(
                        "Aborted multipart upload during cleanup",
                        extra={"s3_key": s3_key, "upload_id": upload_id},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to abort multipart upload",
                        extra={"s3_key": s3_key, "upload_id": upload_id, "error": str(e)},
                    )

            # Delete S3 object if it exists (for completed simple uploads)
            if s3_key and not upload_id:
                try:
                    self.s3_repo.delete_object(s3_key)
                    logger.info("Cleaned up S3 object", extra={"s3_key": s3_key})
                except Exception as e:
                    logger.warning(
                        "Failed to clean up S3 object",
                        extra={"s3_key": s3_key, "error": str(e)},
                    )

            # Delete DynamoDB metadata
            key = {
                "PK": f"VAULT#{vault_id}",
                "SK": f"ITEM#{ItemType.MEDIA}#{item_id}",
            }

            self.items_repo.delete_item(key)
            logger.info("Cleaned up DynamoDB metadata", extra={"item_id": item_id})

        except Exception as e:
            logger.error(
                "Failed to clean up failed upload",
                extra={"vault_id": vault_id, "item_id": item_id, "error": str(e)},
            )
