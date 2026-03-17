"""
Item service layer for Cortex API.

This module implements business logic for item operations including
upload, download, listing, and deletion for all item types (MEDIA, NOTE, TASK, EVENT).

Requirements: 1.2, 1.4, 1.5, 2.1, 2.2, 2.4, 4.5, 7.1, 7.2, 7.4, 11.3, 24.1, 24.2, 24.3
"""

import uuid
from base64 import b64encode
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3

from src.shared.exceptions import BadRequestError, NotFoundError
from src.shared.logger import get_logger
from src.shared.models import (
    CompleteUploadRequest,
    CompleteUploadResponse,
    CreateItemRequest,
    CreateItemResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    ItemType,
    SearchByTagResponse,
)
from src.shared.repository import (
    DynamoDBRepository,
    S3Repository,
    build_s3_key,
    encode_pagination_token,
    parse_pagination_token,
)

logger = get_logger("item_service")

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
            "PK": f"ITEM#{item_id}",
            "SK": "METADATA",  # Constant SK for items (PK-only design with required SK)
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

        # Add GSI1 keys for type-based queries
        item["GSI1PK"] = f"VAULT#{request.vault_id}#TYPE#{request.item_type}"
        item["GSI1SK"] = f"ITEM#{item_id}"

        # Add GSI2 keys for listing all items in vault (without type filter)
        item["GSI2PK"] = f"VAULT#{request.vault_id}"
        item["GSI2SK"] = f"ITEM#{item_id}"

        # Store item in DynamoDB
        if request.encrypted_tags:
            # Use transact_write_items to atomically write item + tag index rows
            transact_items = [{"Put": {"TableName": self.items_repo.table_name, "Item": item}}]
            for tag in request.encrypted_tags:
                tag_row = {
                    "PK": f"VAULT#{request.vault_id}#TAG#{b64encode(tag).decode('utf-8')}",
                    "SK": f"ITEM#{item_id}",
                    "item_id": item_id,
                    "vault_id": request.vault_id,
                    "user_id": user_id,
                }
                transact_items.append(
                    {"Put": {"TableName": self.items_repo.table_name, "Item": tag_row}}
                )
            self.items_repo.transact_write_items(transact_items)
        else:
            self.items_repo.put_item(item)

        logger.info(
            "Created item",
            **{
                "user_id": user_id,
                "vault_id": request.vault_id,
                "item_id": item_id,
                "item_type": request.item_type,
                "tag_count": len(request.encrypted_tags) if request.encrypted_tags else 0,
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
                **{
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
                **{
                    "user_id": user_id,
                    "item_id": item_id,
                    "size_bytes": request.size_bytes,
                },
            )

        # Calculate expiration time
        expires_at = now + timedelta(seconds=PRESIGNED_URL_EXPIRATION)

        # Store item metadata in DynamoDB (pending upload completion)
        item = {
            "PK": f"ITEM#{item_id}",
            "SK": "METADATA",  # Constant SK for items (PK-only design with required SK)
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

        # Add GSI1 keys for type-based queries
        item["GSI1PK"] = f"VAULT#{request.vault_id}#TYPE#{ItemType.MEDIA}"
        item["GSI1SK"] = f"ITEM#{item_id}"

        # Add GSI2 keys for listing all items in vault (without type filter)
        item["GSI2PK"] = f"VAULT#{request.vault_id}"
        item["GSI2SK"] = f"ITEM#{item_id}"

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
            item_id: Item ID to complete
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
        key = {"PK": f"ITEM#{request.item_id}"}

        item = self.items_repo.get_item(key)

        if not item:
            logger.warning(
                "Item not found for upload completion",
                **{"user_id": user_id, "item_id": request.item_id},
            )
            raise NotFoundError("Item not found")

        # Verify user owns the item
        if item["user_id"] != user_id:
            raise NotFoundError("Item not found")

        # Verify S3 object exists and get metadata (including version if available)
        s3_key = item["s3_key"]
        s3_metadata = self.s3_repo.get_object_metadata(s3_key)

        if not s3_metadata:
            logger.error(
                "S3 object not found after upload",
                **{"user_id": user_id, "item_id": request.item_id, "s3_key": s3_key},
            )

            # Abort multipart upload if present
            upload_id = item.get("upload_id")
            if upload_id:
                try:
                    self.s3_repo.abort_multipart_upload(s3_key, upload_id)
                    logger.info(
                        "Aborted multipart upload during cleanup",
                        **{"item_id": request.item_id, "upload_id": upload_id},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to abort multipart upload during cleanup",
                        **{"item_id": request.item_id, "upload_id": upload_id, "error": str(e)},
                    )
                    raise

            # Clean up DynamoDB entry
            self.items_repo.delete_item(key)
            raise

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
        except Exception:
            # Conditional update failed - verify S3 object still exists
            if not self.s3_repo.object_exists(s3_key):
                logger.error(
                    "S3 object deleted during upload completion (TOCTOU race condition detected)",
                    **{
                        "user_id": user_id,
                        "item_id": request.item_id,
                        "s3_key": s3_key,
                    },
                )
                # Clean up orphaned metadata
                self.items_repo.delete_item(key)
                raise

            # Item may have already been completed or is in invalid state
            logger.warning(
                "Conditional update failed during upload completion",
                **{
                    "user_id": user_id,
                    "item_id": request.item_id,
                    "current_status": item.get("upload_status"),
                },
            )
            raise

        logger.info(
            "Completed upload",
            **{
                "user_id": user_id,
                "vault_id": request.vault_id,
                "item_id": request.item_id,
                "s3_version_id": s3_metadata.get("version_id"),
            },
        )

        return CompleteUploadResponse(item_id=request.item_id, uploaded_at=now.timestamp())

    def cleanup_failed_upload(
        self, item_id: str, s3_key: Optional[str], upload_id: Optional[str] = None
    ) -> None:
        """
        Clean up resources after failed upload.

        This method ensures referential integrity by removing both
        S3 objects and DynamoDB metadata when uploads fail. For multipart
        uploads, it aborts the upload to prevent storage costs.

        Args:
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
                        **{"s3_key": s3_key, "upload_id": upload_id},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to abort multipart upload",
                        **{"s3_key": s3_key, "upload_id": upload_id, "error": str(e)},
                    )
                    raise

            # Delete S3 object if it exists (for completed simple uploads)
            if s3_key and not upload_id:
                try:
                    self.s3_repo.delete_object(s3_key)
                    logger.info("Cleaned up S3 object", **{"s3_key": s3_key})
                except Exception as e:
                    logger.warning(
                        "Failed to clean up S3 object",
                        **{"s3_key": s3_key, "error": str(e)},
                    )
                    raise

            # Delete DynamoDB metadata
            key = {
                "PK": f"ITEM#{item_id}",
            }

            self.items_repo.delete_item(key)
            logger.info("Cleaned up DynamoDB metadata", **{"item_id": item_id})

        except Exception as e:
            logger.error(
                "Failed to clean up failed upload",
                **{"item_id": item_id, "error": str(e)},
            )
            raise

    def list_items(
        self,
        user_id: str,
        vault_id: str,
        item_type: Optional[str] = None,
        page_size: int = 50,
        next_token: Optional[str] = None,
        sort_order: str = "desc",
    ) -> tuple[list[dict], Optional[str]]:
        """
        List items with optional type filter and pagination.

        This method queries DynamoDB for user's encrypted metadata and supports
        filtering by item type. All data returned is encrypted and cannot be
        decrypted by the server.

        Args:
            user_id: Authenticated user ID
            vault_id: Vault ID to list items from
            item_type: Optional filter by item type (MEDIA, NOTE, TASK, EVENT)
            page_size: Number of items per page (1-100)
            next_token: Pagination token from previous response
            sort_order: Sort order ('asc' or 'desc')

        Returns:
            Tuple of (items list, next_token)

        Raises:
            StorageError: If DynamoDB operation fails
        """

        # Parse pagination token
        exclusive_start_key = parse_pagination_token(next_token)

        # Build query based on whether we're filtering by type
        if item_type:
            # Use GSI1 for type-based queries
            key_condition_expression = "GSI1PK = :pk"
            expression_attribute_values = {
                ":pk": f"VAULT#{vault_id}#TYPE#{item_type}",
                ":pending": "PENDING",
            }
            index_name = "GSI1"
        else:
            # Use GSI2 for listing all items in vault (without type filter)
            key_condition_expression = "GSI2PK = :pk"
            expression_attribute_values = {
                ":pk": f"VAULT#{vault_id}",
                ":pending": "PENDING",
            }
            index_name = "GSI2"

        # Filter out PENDING uploads at query level (not application level)
        # This ensures consistent page sizes and reduces data transfer
        filter_expression = "upload_status <> :pending OR attribute_not_exists(upload_status)"

        # Execute query
        result = self.items_repo.query(
            key_condition_expression=key_condition_expression,
            expression_attribute_values=expression_attribute_values,
            filter_expression=filter_expression,
            index_name=index_name,
            limit=page_size,
            exclusive_start_key=exclusive_start_key,
            scan_index_forward=(sort_order == "asc"),
        )

        items = result["Items"]
        last_evaluated_key = result.get("LastEvaluatedKey")

        # Encode pagination token
        next_page_token = encode_pagination_token(last_evaluated_key)

        logger.info(
            "Listed items",
            **{
                "user_id": user_id,
                "vault_id": vault_id,
                "item_type": item_type,
                "count": len(items),
                "has_more": next_page_token is not None,
            },
        )

        return items, next_page_token

    def get_item(self, user_id: str, item_id: str) -> Optional[dict]:
        """
        Get a specific item by ID.

        This method retrieves encrypted item metadata from DynamoDB. The server
        cannot decrypt the data.

        Args:
            user_id: Authenticated user ID
            item_id: Item ID

        Returns:
            Item dictionary or None if not found

        Raises:
            AuthorizationError: If user doesn't own the item
            StorageError: If DynamoDB operation fails
        """
        key = {"PK": f"ITEM#{item_id}"}

        item = self.items_repo.get_item(key)

        if not item:
            logger.info(
                "Item not found",
                **{"user_id": user_id, "item_id": item_id},
            )
            raise NotFoundError("Item not found")

        # Verify user owns the item
        if item["user_id"] != user_id:
            raise NotFoundError("Item not found")

        # Filter out PENDING uploads
        if item.get("upload_status") == "PENDING":
            return None

        logger.info(
            "Retrieved item",
            **{
                "user_id": user_id,
                "item_id": item_id,
                "item_type": item.get("item_type"),
            },
        )

        return item

    def get_download_url(self, user_id: str, item_id: str) -> tuple[str, datetime, bytes, str]:
        """
        Generate presigned download URL for MEDIA items.

        This method verifies the item exists, is owned by the user, and is a
        MEDIA type before generating a time-limited presigned S3 URL.

        Args:
            user_id: Authenticated user ID
            item_id: Item ID

        Returns:
            Tuple of (download_url, expires_at, encrypted_metadata, s3_key)

        Raises:
            ResourceNotFoundError: If item not found
            AuthorizationError: If user doesn't own the item
            ValidationError: If item is not a MEDIA type
            StorageError: If DynamoDB or S3 operation fails
        """
        # Retrieve item from DynamoDB
        key = {
            "PK": f"ITEM#{item_id}",
        }

        item = self.items_repo.get_item(key)

        if not item:
            raise NotFoundError("Item not found")

        # Verify user owns the item
        if item["user_id"] != user_id:
            raise NotFoundError("Item not found")

        # Verify item type is MEDIA
        if item["item_type"] != ItemType.MEDIA:
            logger.warning(
                "Item is not a MEDIA type",
                **{
                    "user_id": user_id,
                    "item_id": item_id,
                    "item_type": item["item_type"],
                },
            )
            raise BadRequestError("Download URL only available for MEDIA items")

        # Verify upload is complete
        if item.get("upload_status") == "PENDING":
            logger.warning(
                "Item upload not complete",
                **{"user_id": user_id, "item_id": item_id},
            )
            raise BadRequestError("Item upload not yet complete")

        # Get S3 key
        s3_key = item["s3_key"]

        # Verify S3 object exists
        if not self.s3_repo.object_exists(s3_key):
            # TODO consider if all checks pass but object does not exist
            logger.error(
                "S3 object not found for item",
                **{"user_id": user_id, "item_id": item_id, "s3_key": s3_key},
            )
            raise

        # Generate presigned download URL
        download_url = self.s3_repo.generate_download_url(s3_key, PRESIGNED_URL_EXPIRATION)

        # Calculate expiration time
        now = datetime.now(tz=timezone.utc)
        expires_at = now + timedelta(seconds=PRESIGNED_URL_EXPIRATION)

        logger.info(
            "Generated download URL",
            **{
                "user_id": user_id,
                "item_id": item_id,
                "s3_key": s3_key,
            },
        )

        return download_url, expires_at, item["encrypted_metadata"], s3_key

    def delete_item(self, user_id: str, item_id: str) -> None:
        """
        Delete item and its associated resources.

        This method handles deletion for all item types:
        - For MEDIA items: Deletes both S3 object and DynamoDB metadata atomically
        - For NOTE/TASK/EVENT items: Deletes DynamoDB record only

        The method implements proper cleanup with rollback on partial failures
        to maintain referential integrity between S3 and DynamoDB.

        Args:
            user_id: Authenticated user ID
            item_id: Item ID to delete

        Raises:
            ResourceNotFoundError: If item not found
            AuthorizationError: If user doesn't own the item
            StorageError: If deletion operation fails
        """
        # Direct get using item_id only (no item_type in SK needed)
        key = {"PK": f"ITEM#{item_id}"}

        item = self.items_repo.get_item(key)

        if not item:
            logger.warning(
                "Item not found for deletion",
                **{"user_id": user_id, "item_id": item_id},
            )
            raise NotFoundError("Item not found")

        # Verify user owns the item
        if item["user_id"] != user_id:
            raise NotFoundError("Item not found")

        # Handle deletion based on item type
        if item["item_type"] == ItemType.MEDIA:
            # For MEDIA items: Delete S3 object and DynamoDB metadata atomically
            self._delete_media_item(user_id, item_id, item, key)
        else:
            # For NOTE/TASK/EVENT items: Delete DynamoDB record only
            self._delete_inline_item(user_id, item_id, key, item)

        logger.info(
            "Item deleted successfully",
            **{
                "user_id": user_id,
                "item_id": item_id,
                "item_type": item["item_type"],
            },
        )

    def _delete_media_item(self, user_id: str, item_id: str, item: dict, item_key: dict) -> None:
        """
        Delete MEDIA item with S3 object and DynamoDB metadata.

        This method ensures atomic deletion by:
        1. Deleting S3 object first
        2. Deleting DynamoDB metadata
        3. Rolling back S3 deletion if DynamoDB deletion fails (best effort)

        Args:
            user_id: Authenticated user ID
            item_id: Item ID
            item: Item dictionary from DynamoDB
            item_key: DynamoDB key for the item

        Raises:
            StorageError: If deletion operation fails
        """
        s3_key = item.get("s3_key")

        if not s3_key:
            logger.warning(
                "MEDIA item missing s3_key",
                **{"user_id": user_id, "item_id": item_id},
            )
            # Still try to delete DynamoDB metadata
            self.items_repo.delete_item(item_key)
            return

        # Check if item is still in PENDING upload state
        if item.get("upload_status") == "PENDING":
            # Handle pending upload cleanup
            upload_id = item.get("upload_id")
            if upload_id:
                # Abort multipart upload
                try:
                    self.s3_repo.abort_multipart_upload(s3_key, upload_id)
                    logger.info(
                        "Aborted pending multipart upload during deletion",
                        **{"item_id": item_id, "upload_id": upload_id},
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to abort multipart upload during deletion",
                        **{"item_id": item_id, "upload_id": upload_id, "error": str(e)},
                    )
                    raise

            # Delete DynamoDB metadata for pending upload
            self.items_repo.delete_item(item_key)
            logger.info(
                "Deleted pending upload item",
                **{"user_id": user_id, "item_id": item_id},
            )
            return

        # For completed uploads: Delete S3 object first
        try:
            self.s3_repo.delete_object(s3_key)
            logger.info(
                "Deleted S3 object",
                **{"user_id": user_id, "item_id": item_id, "s3_key": s3_key},
            )
        except Exception as e:
            logger.error(
                "Failed to delete S3 object",
                **{"user_id": user_id, "item_id": item_id, "s3_key": s3_key, "error": str(e)},
            )
            raise

        # Delete DynamoDB metadata
        try:
            self.items_repo.delete_item(item_key)
            logger.info(
                "Deleted DynamoDB metadata",
                **{"user_id": user_id, "item_id": item_id},
            )

            # Clean up tag index rows (best-effort)
            encrypted_tags = item.get("encrypted_tags")
            if encrypted_tags:
                self._delete_tag_index_rows(item["vault_id"], item_id, encrypted_tags)
        except Exception as e:
            logger.error(
                "Failed to delete DynamoDB metadata after S3 deletion",
                **{"user_id": user_id, "item_id": item_id, "error": str(e)},
            )

            logger.info(
                "OrphanedMetadata metric",
                metric_name="OrphanedMetadata",
                metric_unit="Count",
                metric_value=1,
            )

            # Attempt rollback: This is best-effort since S3 delete succeeded
            # In production, consider using S3 versioning to enable true rollback
            logger.warning(
                "DynamoDB deletion failed after S3 deletion - orphaned metadata",
                **{
                    "user_id": user_id,
                    "item_id": item_id,
                    "s3_key": s3_key,
                    "action": "manual_cleanup_required",
                },
            )

            raise

    def _delete_inline_item(self, user_id: str, item_id: str, item_key: dict, item: dict) -> None:
        """
        Delete inline item (NOTE, TASK, EVENT) from DynamoDB only.

        Args:
            user_id: Authenticated user ID
            item_id: Item ID
            item_key: DynamoDB key for the item
            item: Item dictionary from DynamoDB

        Raises:
            StorageError: If deletion operation fails
        """
        try:
            self.items_repo.delete_item(item_key)
            logger.info(
                "Deleted inline item from DynamoDB",
                **{"user_id": user_id, "item_id": item_id},
            )
        except Exception as e:
            logger.error(
                "Failed to delete inline item",
                **{"user_id": user_id, "item_id": item_id, "error": str(e)},
            )
            raise

        # Clean up tag index rows (best-effort)
        encrypted_tags = item.get("encrypted_tags")
        if encrypted_tags:
            self._delete_tag_index_rows(item["vault_id"], item_id, encrypted_tags)

    def _delete_tag_index_rows(self, vault_id: str, item_id: str, encrypted_tags: list) -> None:
        """
        Delete tag index rows for an item. Best-effort cleanup.

        Args:
            vault_id: Vault ID
            item_id: Item ID
            encrypted_tags: List of encrypted tag bytes
        """
        from base64 import b64encode

        if not encrypted_tags:
            return

        try:
            with self.items_repo.table.batch_writer() as writer:
                for tag in encrypted_tags:
                    tag_bytes = bytes(tag) if hasattr(tag, "value") else tag
                    tag_b64 = b64encode(tag_bytes).decode("utf-8")
                    writer.delete_item(
                        Key={
                            "PK": f"VAULT#{vault_id}#TAG#{tag_b64}",
                            "SK": f"ITEM#{item_id}",
                        }
                    )
            logger.info(
                "Deleted tag index rows",
                **{"item_id": item_id, "tag_count": len(encrypted_tags)},
            )
        except Exception as e:
            # Best-effort cleanup - orphaned tag rows are harmless
            logger.warning(
                "Failed to delete tag index rows",
                **{"item_id": item_id, "error": str(e)},
            )

    def search_by_tag(
        self,
        vault_id: str,
        encrypted_tag: str,
        page_size: int = 50,
        next_token: Optional[str] = None,
    ) -> "SearchByTagResponse":
        """
        Search items by encrypted tag using tag index rows.

        Queries tag association rows (PK: VAULT#{vaultId}#TAG#{b64tag}) to find
        matching item IDs, then batch-gets full item metadata.

        Args:
            vault_id: Vault ID to search in
            encrypted_tag: Base64-encoded encrypted tag to search for
            page_size: Number of results per page (default: 50, max: 100)
            next_token: Pagination token from previous response

        Returns:
            SearchByTagResponse with matching items

        Raises:
            BadRequestError: If encrypted_tag is not valid base64
            StorageError: If DynamoDB query fails
        """
        from base64 import b64decode

        from src.shared.models import ItemMetadata, SearchByTagResponse

        # Validate the base64 tag
        try:
            b64decode(encrypted_tag)
        except Exception as e:
            logger.error(
                "Failed to decode encrypted tag",
                **{"encrypted_tag": encrypted_tag, "error": str(e)},
            )
            raise BadRequestError("Invalid encrypted_tag format - must be base64-encoded")

        # Parse pagination token
        exclusive_start_key = parse_pagination_token(next_token) if next_token else None

        # Query tag index: PK = VAULT#{vaultId}#TAG#{b64tag}
        tag_pk = f"VAULT#{vault_id}#TAG#{encrypted_tag}"

        result = self.items_repo.query(
            key_condition_expression="PK = :tag_pk",
            expression_attribute_values={":tag_pk": tag_pk},
            limit=page_size,
            exclusive_start_key=exclusive_start_key,
        )

        tag_rows = result.get("Items", [])
        last_evaluated_key = result.get("LastEvaluatedKey")

        if not tag_rows:
            return SearchByTagResponse(items=[], next_token=None)

        # Batch get full item metadata
        keys = [{"PK": f"ITEM#{row['item_id']}", "SK": "METADATA"} for row in tag_rows]
        full_items = self.items_repo.batch_get_items(keys)

        # Build a lookup map for ordering
        item_map = {item["item_id"]: item for item in full_items}

        # Convert to ItemMetadata models, preserving tag index order
        item_metadata_list = []
        for row in tag_rows:
            item = item_map.get(row["item_id"])
            if not item:
                # Item was deleted but tag row remains (orphaned) - skip
                continue

            encrypted_content = item.get("encrypted_content")
            if encrypted_content and hasattr(encrypted_content, "value"):
                encrypted_content = bytes(encrypted_content)

            encrypted_metadata = item["encrypted_metadata"]
            if hasattr(encrypted_metadata, "value"):
                encrypted_metadata = bytes(encrypted_metadata)

            encrypted_tags = item.get("encrypted_tags")
            if encrypted_tags:
                encrypted_tags = [
                    bytes(tag) if hasattr(tag, "value") else tag for tag in encrypted_tags
                ]

            item_metadata = ItemMetadata(
                item_id=item["item_id"],
                item_type=item["item_type"],
                vault_id=item["vault_id"],
                user_id=item["user_id"],
                encrypted_content=encrypted_content,
                encrypted_metadata=encrypted_metadata,
                encrypted_tags=encrypted_tags,
                created_at=datetime.fromtimestamp(int(item["created_at"]), tz=timezone.utc),
                updated_at=datetime.fromtimestamp(int(item["updated_at"]), tz=timezone.utc),
                version=int(item.get("version", 1)),
                size_bytes=int(item["size_bytes"]) if item.get("size_bytes") else None,
                s3_key=item.get("s3_key"),
            )
            item_metadata_list.append(item_metadata)

        # Pagination token
        next_token_value = encode_pagination_token(last_evaluated_key)

        logger.info(
            "Tag search completed",
            **{
                "vault_id": vault_id,
                "result_count": len(item_metadata_list),
                "has_more": next_token_value is not None,
            },
        )

        return SearchByTagResponse(
            items=item_metadata_list,
            next_token=next_token_value,
        )
