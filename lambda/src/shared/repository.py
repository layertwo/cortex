"""
Shared repository layer for Cortex Backup System.

This module provides data access layer for DynamoDB and S3 operations,
including presigned URL generation and DynamoDB query helpers.

Requirements: 1.4, 1.5, 4.1, 7.1, 7.2
"""

import base64
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from src.shared.exceptions import BadRequestError
from src.shared.logger import get_logger

logger = get_logger("repository")


class DynamoDBRepository:
    """Base repository class for DynamoDB operations."""

    def __init__(self, session: boto3.Session, table_name: str):
        """
        Initialize DynamoDB repository.

        Args:
            table_name: DynamoDB table name (defaults to env variable)
        """
        self._resource = session.resource("dynamodb")
        self.table_name = table_name
        self.table = self._resource.Table(table_name)

    def get_item(self, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get item from DynamoDB by key.

        Args:
            key: Primary key dictionary (PK and SK)

        Returns:
            Item dictionary if found, None otherwise

        Raises:
            StorageError: If DynamoDB operation fails
        """
        try:
            response = self.table.get_item(Key=key)
            return response.get("Item")

        except ClientError as e:
            logger.error(
                "DynamoDB get_item failed",
                **{"error": str(e), "table": self.table_name, "key": key},
            )
            raise

    def put_item(self, item: Dict[str, Any], condition_expression: Optional[str] = None) -> None:
        """
        Put item into DynamoDB.

        Args:
            item: Item dictionary to store
            condition_expression: Optional condition for conditional write

        Raises:
            StorageError: If DynamoDB operation fails
        """
        try:
            kwargs: Dict[str, Any] = {"Item": item}
            if condition_expression:
                kwargs["ConditionExpression"] = condition_expression

            self.table.put_item(**kwargs)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            # Preserve ConditionalCheckFailedException for idempotency handling
            if error_code == "ConditionalCheckFailedException":
                logger.info(
                    "DynamoDB conditional check failed",
                    **{"table": self.table_name, "condition": condition_expression},
                )
                raise BadRequestError(f"Conditional check failed in {self.table_name}")

            logger.error("DynamoDB put_item failed", **{"error": str(e), "table": self.table_name})
            raise

    def update_item(
        self,
        key: Dict[str, Any],
        update_expression: str,
        expression_attribute_values: Dict[str, Any],
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Update item in DynamoDB.

        Args:
            key: Primary key dictionary
            update_expression: DynamoDB update expression
            expression_attribute_values: Values for update expression
            expression_attribute_names: Optional attribute name mappings

        Returns:
            Updated item attributes

        Raises:
            StorageError: If DynamoDB operation fails
        """
        try:
            kwargs = {
                "Key": key,
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }

            if expression_attribute_names:
                kwargs["ExpressionAttributeNames"] = expression_attribute_names

            response = self.table.update_item(**kwargs)
            return response.get("Attributes", {})

        except ClientError as e:
            logger.error(
                "DynamoDB update_item failed",
                **{"error": str(e), "table": self.table_name, "key": key},
            )
            raise

    def update_item_conditional(
        self,
        key: Dict[str, Any],
        update_expression: str,
        condition_expression: str,
        expression_attribute_values: Dict[str, Any],
        expression_attribute_names: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Update item in DynamoDB with condition expression.

        This method prevents race conditions by ensuring the item state
        matches expected conditions before applying the update.

        Args:
            key: Primary key dictionary
            update_expression: DynamoDB update expression
            condition_expression: Condition that must be true for update to succeed
            expression_attribute_values: Values for expressions
            expression_attribute_names: Optional attribute name mappings

        Returns:
            Updated item attributes

        Raises:
            StorageError: If DynamoDB operation fails or condition is not met
        """
        try:
            kwargs = {
                "Key": key,
                "UpdateExpression": update_expression,
                "ConditionExpression": condition_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }

            if expression_attribute_names:
                kwargs["ExpressionAttributeNames"] = expression_attribute_names

            response = self.table.update_item(**kwargs)
            return response.get("Attributes", {})

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            if error_code == "ConditionalCheckFailedException":
                logger.warning(
                    "DynamoDB conditional update failed - condition not met",
                    **{"table": self.table_name, "key": key},
                )
                raise

            logger.error(
                "DynamoDB update_item_conditional failed",
                **{"error": str(e), "table": self.table_name, "key": key},
            )
            raise

    def delete_item(self, key: Dict[str, Any]) -> None:
        """
        Delete item from DynamoDB.

        Args:
            key: Primary key dictionary

        Raises:
            StorageError: If DynamoDB operation fails
        """
        try:
            self.table.delete_item(Key=key)

        except ClientError as e:
            logger.error(
                "DynamoDB delete_item failed",
                **{"error": str(e), "table": self.table_name, "key": key},
            )
            raise

    def transact_write_items(self, transact_items: List[Dict[str, Any]]) -> None:
        """
        Execute a transactional write across multiple items.

        Args:
            transact_items: List of transact item operations (Put, Delete, Update, ConditionCheck)

        Raises:
            ClientError: If transaction fails
        """
        try:
            # transact_write_items is a client-level operation, not table-level
            self.table.meta.client.transact_write_items(TransactItems=transact_items)

        except ClientError as e:
            logger.error(
                "DynamoDB transact_write_items failed",
                **{
                    "error": str(e),
                    "table": self.table_name,
                    "item_count": len(transact_items),
                },
            )
            raise

    def batch_get_items(self, keys: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Batch get multiple items by their primary keys.

        Args:
            keys: List of primary key dictionaries (each with PK and SK)

        Returns:
            List of items found

        Raises:
            ClientError: If batch get fails
        """
        if not keys:
            return []

        try:
            response = self.table.meta.client.batch_get_item(
                RequestItems={self.table_name: {"Keys": keys}}
            )

            items = response.get("Responses", {}).get(self.table_name, [])

            # Handle unprocessed keys with retry
            unprocessed = response.get("UnprocessedKeys", {})
            while unprocessed.get(self.table_name):
                response = self.table.meta.client.batch_get_item(RequestItems=unprocessed)
                items.extend(response.get("Responses", {}).get(self.table_name, []))
                unprocessed = response.get("UnprocessedKeys", {})

            return items

        except ClientError as e:
            logger.error(
                "DynamoDB batch_get_item failed",
                **{"error": str(e), "table": self.table_name, "key_count": len(keys)},
            )
            raise

    def query(
        self,
        key_condition_expression: str,
        expression_attribute_values: Dict[str, Any],
        expression_attribute_names: Optional[Dict[str, str]] = None,
        filter_expression: Optional[str] = None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        exclusive_start_key: Optional[Dict[str, Any]] = None,
        scan_index_forward: bool = True,
    ) -> Dict[str, Any]:
        """
        Query DynamoDB table or index.

        Args:
            key_condition_expression: Key condition expression
            expression_attribute_values: Values for expression
            expression_attribute_names: Optional attribute name mappings
            filter_expression: Optional filter expression to apply after query
            index_name: Optional GSI name
            limit: Optional result limit
            exclusive_start_key: Optional pagination token
            scan_index_forward: Sort order (True=ascending, False=descending)

        Returns:
            Query response with Items and optional LastEvaluatedKey

        Raises:
            StorageError: If DynamoDB operation fails
        """
        try:
            kwargs = {
                "KeyConditionExpression": key_condition_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ScanIndexForward": scan_index_forward,
            }

            if expression_attribute_names:
                kwargs["ExpressionAttributeNames"] = expression_attribute_names

            if filter_expression:
                kwargs["FilterExpression"] = filter_expression

            if index_name:
                kwargs["IndexName"] = index_name

            if limit:
                kwargs["Limit"] = limit

            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = self.table.query(**kwargs)

            return {
                "Items": response.get("Items", []),
                "LastEvaluatedKey": response.get("LastEvaluatedKey"),
            }

        except ClientError as e:
            logger.error(
                "DynamoDB query failed",
                **{"error": str(e), "table": self.table_name, "index": index_name},
            )
            raise


class S3Repository:
    """Repository class for S3 operations and presigned URL generation."""

    def __init__(self, session: boto3.Session, bucket_name: str):
        """
        Initialize S3 repository.

        Args:
            bucket_name: S3 bucket name (defaults to env variable)
        """
        self._client = session.client("s3")
        self.bucket_name = bucket_name

    def generate_upload_url(
        self, object_key: str, content_type: str, expiration: int = 900  # 15 minutes
    ) -> str:
        """
        Generate presigned URL for S3 upload.

        The presigned URL is scoped to the specific object key and allows
        only PUT operations. This enables direct client-to-S3 uploads.

        Args:
            object_key: S3 object key (path)
            content_type: MIME type of the file
            expiration: URL expiration in seconds (default 15 minutes)

        Returns:
            Presigned upload URL

        Raises:
            StorageError: If URL generation fails
        """
        try:
            url = self._client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self.bucket_name, "Key": object_key, "ContentType": content_type},
                ExpiresIn=expiration,
            )

            logger.debug(
                "Generated upload URL", **{"object_key": object_key, "expiration": expiration}
            )

            return url

        except ClientError as e:
            logger.error(
                "Failed to generate upload URL",
                **{"error": str(e), "bucket": self.bucket_name, "key": object_key},
            )
            raise

    def generate_download_url(self, object_key: str, expiration: int = 900) -> str:  # 15 minutes
        """
        Generate presigned URL for S3 download.

        The presigned URL is scoped to the specific object key and allows
        only GET operations. This enables direct client-to-S3 downloads.

        Args:
            object_key: S3 object key (path)
            expiration: URL expiration in seconds (default 15 minutes)

        Returns:
            Presigned download URL

        Raises:
            StorageError: If URL generation fails
        """
        try:
            url = self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_key},
                ExpiresIn=expiration,
            )

            logger.debug(
                "Generated download URL", **{"object_key": object_key, "expiration": expiration}
            )

            return url

        except ClientError as e:
            logger.error(
                "Failed to generate download URL",
                **{"error": str(e), "bucket": self.bucket_name, "key": object_key},
            )
            raise

    def generate_multipart_upload_url(
        self,
        object_key: str,
        content_type: str,
        part_number: int,
        upload_id: str,
        expiration: int = 900,
    ) -> str:
        """
        Generate presigned URL for multipart upload part.

        Args:
            object_key: S3 object key
            content_type: MIME type
            part_number: Part number (1-10000)
            upload_id: Multipart upload ID
            expiration: URL expiration in seconds

        Returns:
            Presigned URL for uploading the part

        Raises:
            StorageError: If URL generation fails
        """
        try:
            url = self._client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": object_key,
                    "PartNumber": part_number,
                    "UploadId": upload_id,
                },
                ExpiresIn=expiration,
            )

            return url

        except ClientError as e:
            logger.error(
                "Failed to generate multipart upload URL",
                **{
                    "error": str(e),
                    "bucket": self.bucket_name,
                    "key": object_key,
                    "part_number": part_number,
                },
            )
            raise

    def initiate_multipart_upload(self, object_key: str, content_type: str) -> str:
        """
        Initiate multipart upload.

        Args:
            object_key: S3 object key
            content_type: MIME type

        Returns:
            Upload ID for the multipart upload

        Raises:
            StorageError: If initiation fails
        """
        try:
            response = self._client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            )

            upload_id = response["UploadId"]

            logger.info(
                "Initiated multipart upload",
                **{"object_key": object_key, "upload_id": upload_id},
            )

            return upload_id

        except ClientError as e:
            logger.error(
                "Failed to initiate multipart upload",
                **{"error": str(e), "bucket": self.bucket_name, "key": object_key},
            )
            raise

    def abort_multipart_upload(self, object_key: str, upload_id: str) -> None:
        """
        Abort multipart upload and clean up parts.

        Args:
            object_key: S3 object key
            upload_id: Multipart upload ID to abort

        Raises:
            StorageError: If abort fails
        """
        try:
            self._client.abort_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                UploadId=upload_id,
            )

            logger.info(
                "Aborted multipart upload",
                **{"object_key": object_key, "upload_id": upload_id},
            )

        except ClientError as e:
            logger.error(
                "Failed to abort multipart upload",
                **{
                    "error": str(e),
                    "bucket": self.bucket_name,
                    "key": object_key,
                    "upload_id": upload_id,
                },
            )
            raise

    def complete_multipart_upload(
        self, object_key: str, upload_id: str, parts: list[dict]
    ) -> None:
        """
        Complete a multipart upload, assembling the staged parts into one object.

        Args:
            object_key: S3 object key
            upload_id: Multipart upload ID
            parts: Ordered list of {"PartNumber": int, "ETag": str}

        Raises:
            ClientError: If S3 rejects the completion (e.g. missing/mismatched parts)
        """
        try:
            self._client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            logger.info(
                "Completed multipart upload",
                **{"object_key": object_key, "upload_id": upload_id, "part_count": len(parts)},
            )
        except ClientError as e:
            logger.error(
                "Failed to complete multipart upload",
                **{
                    "error": str(e),
                    "bucket": self.bucket_name,
                    "key": object_key,
                    "upload_id": upload_id,
                },
            )
            raise

    def delete_object(self, object_key: str) -> None:
        """
        Delete object from S3.

        Args:
            object_key: S3 object key to delete

        Raises:
            StorageError: If deletion fails
        """
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=object_key)

            logger.info("Deleted S3 object", **{"object_key": object_key})

        except ClientError as e:
            logger.error(
                "Failed to delete S3 object",
                **{"error": str(e), "bucket": self.bucket_name, "key": object_key},
            )
            raise

    def object_exists(self, object_key: str) -> bool:
        """
        Check if object exists in S3.

        Args:
            object_key: S3 object key

        Returns:
            True if object exists, False otherwise
        """
        try:
            self._client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False

            logger.error(
                "Failed to check object existence",
                **{"error": str(e), "bucket": self.bucket_name, "key": object_key},
            )
            raise

    def get_object_metadata(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Get object metadata from S3 including version ID if available.

        This method retrieves object metadata which can be used to verify
        object existence and track specific versions in versioned buckets.

        Args:
            object_key: S3 object key

        Returns:
            Dictionary with metadata (version_id, content_length, etag, etc.)
            or None if object doesn't exist

        Raises:
            StorageError: If S3 operation fails (excluding 404)
        """
        try:
            response = self._client.head_object(Bucket=self.bucket_name, Key=object_key)

            metadata = {
                "content_length": response.get("ContentLength"),
                "etag": response.get("ETag"),
                "last_modified": response.get("LastModified"),
            }

            # Include version ID if bucket has versioning enabled
            if "VersionId" in response:
                metadata["version_id"] = response["VersionId"]

            return metadata

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None

            logger.error(
                "Failed to get object metadata",
                **{"error": str(e), "bucket": self.bucket_name, "key": object_key},
            )
            raise


def build_s3_key(vault_id: str, file_id: str) -> str:
    """
    Build S3 object key for a file.

    Format: vaults/{vaultId}/files/{fileId}/{timestamp}-{random}

    Args:
        vault_id: Vault ID
        file_id: File ID

    Returns:
        S3 object key
    """

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:8]

    return f"vaults/{vault_id}/files/{file_id}/{timestamp}-{random_suffix}"


def parse_pagination_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Parse pagination token from client.

    Args:
        token: Base64-encoded pagination token

    Returns:
        Decoded DynamoDB LastEvaluatedKey or None
    """
    if not token:
        return None

    try:
        decoded = base64.b64decode(token)

        # Prevent DoS via oversized tokens (limit to 1KB of decoded data)
        if len(decoded) > 1024:
            logger.warning("Pagination token too large", **{"decoded_size": len(decoded)})
            return None

        return json.loads(decoded)

    except Exception as e:
        logger.warning("Failed to parse pagination token", **{"error": str(e)})
        return None


def encode_pagination_token(last_evaluated_key: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Encode DynamoDB LastEvaluatedKey as pagination token.

    Args:
        last_evaluated_key: DynamoDB LastEvaluatedKey

    Returns:
        Base64-encoded pagination token or None
    """
    if not last_evaluated_key:
        return None

    try:

        json_str = json.dumps(last_evaluated_key)
        encoded = base64.b64encode(json_str.encode("utf-8"))
        return encoded.decode("utf-8")

    except Exception as e:
        logger.error("Failed to encode pagination token", **{"error": str(e)})
        return None
