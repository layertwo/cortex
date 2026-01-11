"""
Shared data models for Cortex Backup System.

This module defines Pydantic models for request/response validation
and DynamoDB item structures.

Requirements: 8.1, 8.3
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Request/Response Models for API Operations
# ============================================================================


class InitiateUploadRequest(BaseModel):
    """Request model for initiating file upload."""

    encrypted_metadata: bytes = Field(
        ..., description="Encrypted file metadata (filename, size, MIME type, etc.)"
    )
    size_bytes: int = Field(..., gt=0, description="File size in bytes")
    content_type: str = Field(..., description="MIME type of the file")
    vault_id: str = Field(..., description="Vault ID for the file")
    encrypted_tags: Optional[List[bytes]] = Field(
        default=None, description="List of encrypted tags"
    )


class InitiateUploadResponse(BaseModel):
    """Response model for upload initiation."""

    file_id: str = Field(..., description="Unique file identifier")
    upload_url: str = Field(..., description="Presigned S3 upload URL")
    expires_at: datetime = Field(..., description="URL expiration timestamp")
    s3_key: str = Field(..., description="S3 object key")
    upload_id: Optional[str] = Field(
        default=None, description="Multipart upload ID (for large files)"
    )


class CompleteUploadRequest(BaseModel):
    """Request model for completing file upload."""

    file_id: str = Field(..., description="File identifier from initiation")
    vault_id: str = Field(..., description="Vault ID")


class CompleteUploadResponse(BaseModel):
    """Response model for upload completion."""

    file_id: str = Field(..., description="File identifier")
    uploaded_at: datetime = Field(..., description="Upload completion timestamp")


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


class AddMediaToCollectionRequest(BaseModel):
    """Request model for adding media to collection."""

    collection_id: str = Field(..., description="Collection identifier")
    file_id: str = Field(..., description="File identifier")
    vault_id: str = Field(..., description="Vault ID")


class AddMediaToCollectionResponse(BaseModel):
    """Response model for adding media to collection."""

    collection_id: str = Field(..., description="Collection identifier")
    file_id: str = Field(..., description="File identifier")
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

    items: List[MediaItem] = Field(..., description="Matching media items")
    next_token: Optional[str] = Field(default=None, description="Pagination token")


# ============================================================================
# Vault Models
# ============================================================================


class CreateVaultRequest(BaseModel):
    """Request model for creating a vault."""

    vault_salt: bytes = Field(
        ..., min_length=16, max_length=16, description="16-byte vault salt for key derivation"
    )


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


class DynamoDBFileCollectionAssociation(BaseModel):
    """DynamoDB item model for file-collection associations."""

    PK: str = Field(..., description="Partition key: COLLECTION#{collectionId}")
    SK: str = Field(..., description="Sort key: FILE#{fileId}")
    collection_id: str = Field(..., description="Collection identifier")
    file_id: str = Field(..., description="File identifier")
    vault_id: str = Field(..., description="Vault identifier")
    user_id: str = Field(..., description="User identifier")
    added_at: int = Field(..., description="Addition timestamp (Unix epoch)")
    GSI1PK: str = Field(..., description="GSI1 PK: FILE#{fileId}")
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
