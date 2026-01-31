"""
Shared data models for Cortex Backup System.

This module defines Pydantic models for request/response validation
and DynamoDB item structures.

Requirements: 8.1, 8.3
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

# ============================================================================
# Enums
# ============================================================================


class ItemType(str):
    """Item type enumeration."""

    MEDIA = "MEDIA"
    NOTE = "NOTE"
    TASK = "TASK"
    EVENT = "EVENT"


# ============================================================================
# Request/Response Models for API Operations
# ============================================================================


class CreateItemRequest(BaseModel):
    """Request model for creating items (NOTE, TASK, EVENT with inline content)."""

    vault_id: str = Field(..., description="Vault ID for the item")
    item_type: str = Field(..., description="Item type: NOTE, TASK, or EVENT")
    encrypted_content: bytes = Field(..., description="Encrypted item content as JSON blob")
    encrypted_metadata: bytes = Field(..., description="Encrypted item metadata")
    encrypted_tags: Optional[List[bytes]] = Field(
        default=None, description="List of encrypted tags"
    )
    encrypted_date_bucket: Optional[bytes] = Field(
        default=None, description="Encrypted date bucket for tasks/events"
    )
    time_bucket: Optional[str] = Field(
        default=None, description="Plaintext 15-min time bucket for server queries"
    )

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        """Validate item type value."""
        if v not in [ItemType.NOTE, ItemType.TASK, ItemType.EVENT]:
            raise ValueError("item_type must be NOTE, TASK, or EVENT for inline content")
        return v


class CreateItemResponse(BaseModel):
    """Response model for item creation."""

    item_id: str = Field(..., description="Unique item identifier")
    item_type: str = Field(..., description="Item type")
    created_at: datetime = Field(..., description="Creation timestamp")


class InitiateUploadRequest(BaseModel):
    """Request model for initiating MEDIA file upload."""

    vault_id: str = Field(..., description="Vault ID for the file")
    encrypted_metadata: bytes = Field(
        ..., description="Encrypted file metadata (filename, size, MIME type, etc.)"
    )
    size_bytes: int = Field(..., gt=0, le=5_368_709_120, description="File size in bytes (max 5GB)")
    content_type: str = Field(..., description="MIME type of the file")
    encrypted_tags: Optional[List[bytes]] = Field(
        default=None, description="List of encrypted tags"
    )


class InitiateUploadResponse(BaseModel):
    """Response model for MEDIA upload initiation."""

    item_id: str = Field(..., description="Unique item identifier")
    upload_url: str = Field(..., description="Presigned S3 upload URL")
    expires_at: datetime = Field(..., description="URL expiration timestamp")
    s3_key: str = Field(..., description="S3 object key")
    upload_id: Optional[str] = Field(
        default=None, description="Multipart upload ID (for large files >100MB)"
    )


class CompleteUploadRequest(BaseModel):
    """Request model for completing MEDIA file upload."""

    item_id: str = Field(..., description="Item identifier from initiation")
    vault_id: str = Field(..., description="Vault ID")


class CompleteUploadResponse(BaseModel):
    """Response model for MEDIA upload completion."""

    item_id: str = Field(..., description="Item identifier")
    uploaded_at: datetime = Field(..., description="Upload completion timestamp")


class ListItemsRequest(BaseModel):
    """Request model for listing items with optional filters."""

    vault_id: str = Field(..., description="Vault ID to list items from")
    item_type: Optional[str] = Field(
        default=None, description="Optional filter by item type: MEDIA, NOTE, TASK, EVENT"
    )
    page_size: int = Field(default=50, ge=1, le=100, description="Number of items per page")
    next_token: Optional[str] = Field(
        default=None, description="Pagination token from previous response"
    )
    sort_order: str = Field(default="desc", description="Sort order: 'asc' or 'desc'")

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        """Validate sort order value."""
        if v not in ["asc", "desc"]:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return v

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate item type value."""
        if v is not None and v not in [
            ItemType.MEDIA,
            ItemType.NOTE,
            ItemType.TASK,
            ItemType.EVENT,
        ]:
            raise ValueError("item_type must be MEDIA, NOTE, TASK, or EVENT")
        return v


class ListMediaRequest(BaseModel):
    """Request model for listing media files."""

    vault_id: str = Field(..., description="Vault ID to list files from")
    page_size: int = Field(default=50, ge=1, le=100, description="Number of items per page")
    next_token: Optional[str] = Field(
        default=None, description="Pagination token from previous response"
    )
    sort_order: str = Field(default="desc", description="Sort order: 'asc' or 'desc'")

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: str) -> str:
        """Validate sort order value."""
        if v not in ["asc", "desc"]:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return v


class ItemMetadata(BaseModel):
    """Model for an item with encrypted metadata."""

    item_id: str = Field(..., description="Unique item identifier")
    item_type: str = Field(..., description="Item type: MEDIA, NOTE, TASK, EVENT")
    vault_id: str = Field(..., description="Vault ID")
    user_id: str = Field(..., description="Owner user ID")
    encrypted_content: Optional[bytes] = Field(
        default=None, description="Encrypted content (for NOTE, TASK, EVENT)"
    )
    encrypted_metadata: bytes = Field(..., description="Encrypted item metadata")
    encrypted_tags: Optional[List[bytes]] = Field(default=None, description="Encrypted tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    version: int = Field(..., description="Version number for conflict resolution")
    size_bytes: Optional[int] = Field(default=None, description="File size (for MEDIA items)")
    s3_key: Optional[str] = Field(default=None, description="S3 object key (for MEDIA items)")


class ListItemsResponse(BaseModel):
    """Response model for item listing."""

    items: List[ItemMetadata] = Field(..., description="List of items")
    next_token: Optional[str] = Field(
        default=None, description="Token for next page (if more results available)"
    )


class GetItemResponse(BaseModel):
    """Response model for getting a single item."""

    item_id: str = Field(..., description="Item identifier")
    item_type: str = Field(..., description="Item type: MEDIA, NOTE, TASK, EVENT")
    vault_id: str = Field(..., description="Vault ID")
    encrypted_content: Optional[bytes] = Field(
        default=None, description="Encrypted content (for NOTE, TASK, EVENT)"
    )
    encrypted_metadata: bytes = Field(..., description="Encrypted metadata")
    encrypted_tags: Optional[List[bytes]] = Field(default=None, description="Encrypted tags")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    size_bytes: Optional[int] = Field(default=None, description="File size (for MEDIA items)")
    s3_key: Optional[str] = Field(default=None, description="S3 object key (for MEDIA items)")


class MediaItem(BaseModel):
    """Model for a media file item."""

    file_id: str = Field(..., description="Unique file identifier")
    vault_id: str = Field(..., description="Vault ID")
    user_id: str = Field(..., description="Owner user ID")
    s3_key: str = Field(..., description="S3 object key")
    encrypted_metadata: bytes = Field(..., description="Encrypted file metadata")
    encrypted_tags: Optional[List[bytes]] = Field(default=None, description="Encrypted tags")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    size_bytes: int = Field(..., description="File size in bytes")


class ListMediaResponse(BaseModel):
    """Response model for media listing."""

    items: List[MediaItem] = Field(..., description="List of media items")
    next_token: Optional[str] = Field(
        default=None, description="Token for next page (if more results available)"
    )
    total_count: Optional[int] = Field(default=None, description="Total count (if available)")


class GetDownloadUrlRequest(BaseModel):
    """Request model for getting download URL."""

    file_id: str = Field(..., description="File identifier")
    vault_id: str = Field(..., description="Vault ID")


class GetDownloadUrlResponse(BaseModel):
    """Response model for download URL."""

    download_url: str = Field(..., description="Presigned S3 download URL")
    expires_at: datetime = Field(..., description="URL expiration timestamp")
    encrypted_metadata: bytes = Field(..., description="Encrypted file metadata")
    item_id: str = Field(..., description="Item identifier")
    s3_key: str = Field(..., description="S3 object key")


class DeleteMediaRequest(BaseModel):
    """Request model for deleting media."""

    file_id: str = Field(..., description="File identifier")
    vault_id: str = Field(..., description="Vault ID")


class DeleteMediaResponse(BaseModel):
    """Response model for media deletion."""

    file_id: str = Field(..., description="Deleted file identifier")
    deleted_at: datetime = Field(..., description="Deletion timestamp")


# ============================================================================
# Collection Models
# ============================================================================


class CreateCollectionRequest(BaseModel):
    """Request model for creating a collection."""

    vault_id: str = Field(..., description="Vault ID")
    encrypted_metadata: bytes = Field(
        ..., description="Encrypted collection metadata (name, description, etc.)"
    )


class CreateCollectionResponse(BaseModel):
    """Response model for collection creation."""

    collection_id: str = Field(..., description="Unique collection identifier")
    created_at: datetime = Field(..., description="Creation timestamp")


class CollectionItem(BaseModel):
    """Model for a collection."""

    collection_id: str = Field(..., description="Collection identifier")
    vault_id: str = Field(..., description="Vault ID")
    user_id: str = Field(..., description="Owner user ID")
    encrypted_metadata: bytes = Field(..., description="Encrypted collection metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    item_count: int = Field(default=0, description="Number of items in collection")


class ListCollectionsResponse(BaseModel):
    """Response model for listing collections."""

    items: List[CollectionItem] = Field(..., description="List of collections")
    next_token: Optional[str] = Field(default=None, description="Pagination token")


class UpdateCollectionRequest(BaseModel):
    """Request model for updating a collection."""

    collection_id: str = Field(..., description="Collection identifier")
    vault_id: str = Field(..., description="Vault ID")
    encrypted_metadata: bytes = Field(..., description="Updated encrypted metadata")


class UpdateCollectionResponse(BaseModel):
    """Response model for collection update."""

    collection_id: str = Field(..., description="Collection identifier")
    updated_at: datetime = Field(..., description="Update timestamp")


class AddItemToCollectionRequest(BaseModel):
    """Request model for adding items to collection."""

    collection_id: str = Field(..., description="Collection identifier")
    item_id: str = Field(..., description="Item identifier")
    vault_id: str = Field(..., description="Vault ID")


class AddItemToCollectionResponse(BaseModel):
    """Response model for adding items to collection."""

    collection_id: str = Field(..., description="Collection identifier")
    item_id: str = Field(..., description="Item identifier")
    added_at: datetime = Field(..., description="Addition timestamp")


# ============================================================================
# Tag Search Models
# ============================================================================


class SearchByTagRequest(BaseModel):
    """Request model for tag search."""

    vault_id: str = Field(..., description="Vault ID to search in")
    encrypted_tag: bytes = Field(..., description="Encrypted tag to search for")
    page_size: int = Field(default=50, ge=1, le=100, description="Results per page")
    next_token: Optional[str] = Field(default=None, description="Pagination token")


class SearchByTagResponse(BaseModel):
    """Response model for tag search."""

    items: List[ItemMetadata] = Field(..., description="Matching items")
    next_token: Optional[str] = Field(default=None, description="Pagination token")


# ============================================================================
# Vault Models
# ============================================================================


class CreateVaultRequest(BaseModel):
    """Request model for creating a vault."""

    vault_salt: Optional[bytes] = Field(
        default=None,
        min_length=16,
        max_length=16,
        description=(
            "Optional 16-byte vault salt for key derivation " "(if not provided, will be generated)"
        ),
    )

    @field_validator("vault_salt", mode="before")
    @classmethod
    def decode_vault_salt(cls, v: Any) -> Optional[bytes]:
        """Decode base64-encoded vault salt from JSON."""
        if v is None:
            return None
        if isinstance(v, bytes):
            return v
        if isinstance(v, str):
            try:
                return base64.b64decode(v)
            except Exception as e:
                raise ValueError(f"Invalid base64-encoded vault_salt: {e}")
        raise ValueError("vault_salt must be a base64-encoded string or bytes")


class CreateVaultResponse(BaseModel):
    """Response model for vault creation."""

    vault_id: str = Field(..., description="Unique vault identifier")
    created_at: datetime = Field(..., description="Creation timestamp")


class GetVaultSaltRequest(BaseModel):
    """Request model for retrieving vault salt."""

    vault_id: str = Field(..., description="Vault identifier")


class GetVaultSaltResponse(BaseModel):
    """Response model for vault salt retrieval."""

    vault_id: str = Field(..., description="Vault identifier")
    vault_salt: bytes = Field(..., description="16-byte vault salt")

    @field_serializer("vault_salt")
    def serialize_vault_salt(self, vault_salt: bytes, _info) -> str:
        """Serialize vault salt as base64-encoded string."""
        return base64.b64encode(vault_salt).decode("utf-8")


# ============================================================================
# Share Models
# ============================================================================


class CreateShareRequest(BaseModel):
    """Request model for creating a file share."""

    file_id: str = Field(..., description="File identifier to share")
    vault_id: str = Field(..., description="Vault ID")
    expires_at: Optional[datetime] = Field(
        default=None, description="Optional expiration timestamp"
    )
    is_password_protected: bool = Field(
        default=False, description="Whether share requires password"
    )


class CreateShareResponse(BaseModel):
    """Response model for share creation."""

    share_id: str = Field(..., description="Unique share identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")


class GetShareRequest(BaseModel):
    """Request model for accessing a share."""

    share_id: str = Field(..., description="Share identifier")


class GetShareResponse(BaseModel):
    """Response model for share access."""

    share_id: str = Field(..., description="Share identifier")
    file_id: str = Field(..., description="File identifier")
    download_url: str = Field(..., description="Presigned download URL")
    encrypted_metadata: bytes = Field(..., description="Encrypted file metadata")
    expires_at: datetime = Field(..., description="URL expiration")
    is_password_protected: bool = Field(default=False, description="Whether password is required")


class RevokeShareRequest(BaseModel):
    """Request model for revoking a share."""

    share_id: str = Field(..., description="Share identifier")


class RevokeShareResponse(BaseModel):
    """Response model for share revocation."""

    share_id: str = Field(..., description="Share identifier")
    revoked_at: datetime = Field(..., description="Revocation timestamp")


# ============================================================================
# Account Recovery Models
# ============================================================================


class GenerateRecoveryCodesRequest(BaseModel):
    """Request model for generating account recovery codes."""

    user_id: str = Field(..., description="User identifier")


class GenerateRecoveryCodesResponse(BaseModel):
    """Response model for recovery code generation."""

    recovery_codes: List[str] = Field(..., description="List of recovery codes (displayed once)")
    generated_at: datetime = Field(..., description="Generation timestamp")


class ValidateRecoveryCodeRequest(BaseModel):
    """Request model for validating recovery code."""

    user_id: str = Field(..., description="User identifier")
    recovery_code: str = Field(..., description="Recovery code to validate")


class ValidateRecoveryCodeResponse(BaseModel):
    """Response model for recovery code validation."""

    valid: bool = Field(..., description="Whether code is valid")
    user_id: str = Field(..., description="User identifier")


# ============================================================================
# DynamoDB Item Models
# ============================================================================


class DynamoDBItemModel(BaseModel):
    """DynamoDB item model for all item types (MEDIA, NOTE, TASK, EVENT)."""

    PK: str = Field(..., description="Partition key: VAULT#{vaultId}")
    SK: str = Field(..., description="Sort key: ITEM#{itemId}")
    item_id: str = Field(..., description="Item identifier")
    item_type: str = Field(..., description="Item type: MEDIA, NOTE, TASK, EVENT")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="User identifier")
    encrypted_content: Optional[bytes] = Field(
        default=None, description="Encrypted content (for NOTE, TASK, EVENT)"
    )
    encrypted_metadata: bytes = Field(..., description="Encrypted metadata")
    encrypted_tags: Optional[List[bytes]] = Field(default=None, description="Encrypted tags")
    encrypted_date_bucket: Optional[bytes] = Field(
        default=None, description="Encrypted date bucket (for TASK, EVENT)"
    )
    time_bucket: Optional[str] = Field(
        default=None, description="Plaintext 15-min time bucket for queries"
    )
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")
    updated_at: int = Field(..., description="Update timestamp (Unix epoch)")
    version: int = Field(default=1, description="Version number for conflict resolution")
    size_bytes: Optional[int] = Field(default=None, description="File size (for MEDIA items)")
    s3_key: Optional[str] = Field(default=None, description="S3 object key (for MEDIA items)")
    upload_status: Optional[str] = Field(
        default=None, description="Upload status: PENDING or COMPLETE (for MEDIA items)"
    )
    ttl: Optional[int] = Field(
        default=None,
        description="TTL for auto-expiration (Unix epoch, for PENDING uploads only)",
    )
    GSI1PK: Optional[str] = Field(
        default=None, description="GSI1 PK: VAULT#{vaultId}#TYPE#{itemType}"
    )
    GSI1SK: Optional[str] = Field(default=None, description="GSI1 SK: ITEM#{itemId}")
    GSI2PK: Optional[str] = Field(
        default=None, description="GSI2 PK: VAULT#{vaultId}#TYPE#{itemType}#DATE#{timeBucket}"
    )
    GSI2SK: Optional[str] = Field(default=None, description="GSI2 SK: ITEM#{itemId}")
    GSI3PK: Optional[str] = Field(
        default=None, description="GSI3 PK: VAULT#{vaultId}#TAG#{encryptedTag}"
    )
    GSI3SK: Optional[str] = Field(default=None, description="GSI3 SK: ITEM#{itemId}")


class DynamoDBFileItem(BaseModel):
    """DynamoDB item model for files."""

    PK: str = Field(..., description="Partition key: VAULT#{vaultId}")
    SK: str = Field(..., description="Sort key: FILE#{fileId}")
    file_id: str = Field(..., description="File identifier")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="User identifier")
    s3_key: str = Field(..., description="S3 object key")
    encrypted_metadata: bytes = Field(..., description="Encrypted metadata")
    encrypted_tags: Optional[List[bytes]] = Field(default=None, description="Encrypted tags")
    uploaded_at: int = Field(..., description="Upload timestamp (Unix epoch)")
    size_bytes: int = Field(..., description="File size in bytes")
    GSI1PK: Optional[str] = Field(default=None, description="GSI1 partition key for tag queries")
    GSI1SK: Optional[str] = Field(default=None, description="GSI1 sort key for tag queries")


class DynamoDBVaultItem(BaseModel):
    """DynamoDB item model for vaults."""

    PK: str = Field(..., description="Partition key: USER#{userId}")
    SK: str = Field(..., description="Sort key: VAULT#{vaultId}")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="User identifier")
    vault_salt: bytes = Field(..., description="16-byte vault salt")
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")


class DynamoDBCollectionItem(BaseModel):
    """DynamoDB item model for collections."""

    PK: str = Field(..., description="Partition key: VAULT#{vaultId}")
    SK: str = Field(..., description="Sort key: COLLECTION#{collectionId}")
    collection_id: str = Field(..., description="Collection identifier")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="User identifier")
    encrypted_metadata: bytes = Field(..., description="Encrypted metadata")
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")
    updated_at: int = Field(..., description="Update timestamp (Unix epoch)")
    item_count: int = Field(default=0, description="Number of items")


class DynamoDBItemCollectionAssociation(BaseModel):
    """DynamoDB item model for item-collection associations."""

    PK: str = Field(..., description="Partition key: COLLECTION#{collectionId}")
    SK: str = Field(..., description="Sort key: ITEM#{itemId}")
    collection_id: str = Field(..., description="Collection identifier")
    item_id: str = Field(..., description="Item identifier")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="User identifier")
    added_at: int = Field(..., description="Addition timestamp (Unix epoch)")
    GSI1PK: str = Field(..., description="GSI1 PK: ITEM#{itemId}")
    GSI1SK: str = Field(..., description="GSI1 SK: COLLECTION#{collectionId}")


class DynamoDBShareItem(BaseModel):
    """DynamoDB item model for shares."""

    PK: str = Field(..., description="Partition key: SHARE#{shareId}")
    SK: str = Field(..., description="Sort key: METADATA")
    share_id: str = Field(..., description="Share identifier")
    file_id: str = Field(..., description="File identifier")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="Owner user identifier")
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")
    expires_at: Optional[int] = Field(default=None, description="Expiration timestamp (Unix epoch)")
    is_password_protected: bool = Field(default=False, description="Password protection flag")
    is_revoked: bool = Field(default=False, description="Revocation flag")
    access_count: int = Field(default=0, description="Access counter")
    last_accessed_at: Optional[int] = Field(default=None, description="Last access timestamp")


class DynamoDBRecoveryCodeItem(BaseModel):
    """DynamoDB item model for account recovery codes."""

    PK: str = Field(..., description="Partition key: USER#{userId}")
    SK: str = Field(..., description="Sort key: RECOVERY#{codeHash}")
    user_id: str = Field(..., description="User identifier")
    code_hash: str = Field(..., description="SHA-256 hash of recovery code")
    created_at: int = Field(..., description="Creation timestamp (Unix epoch)")
    used_at: Optional[int] = Field(default=None, description="Usage timestamp (Unix epoch)")
    is_valid: bool = Field(default=True, description="Validity flag")


# ============================================================================
# Error Response Model
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: Dict[str, Any] = Field(..., description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "Authentication required",
                    "requestId": "abc-123-def-456",
                    "timestamp": "2024-01-01T00:00:00Z",
                }
            }
        }
