"""
Unit tests for shared/models.py module.

Tests Pydantic models for request/response validation.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.shared.models import (
    CollectionItem,
    CompleteUploadRequest,
    CreateCollectionRequest,
    CreateShareRequest,
    CreateVaultRequest,
    DynamoDBFileItem,
    DynamoDBRecoveryCodeItem,
    DynamoDBShareItem,
    DynamoDBVaultItem,
    ErrorResponse,
    GenerateRecoveryCodesResponse,
    InitiateUploadRequest,
    InitiateUploadResponse,
    ListMediaRequest,
    MediaItem,
    SearchByTagRequest,
    ValidateRecoveryCodeRequest,
)


class TestInitiateUploadRequest:
    """Tests for InitiateUploadRequest model."""

    def test_valid_request(self):
        """Should create valid request."""
        request = InitiateUploadRequest(
            encrypted_metadata=b"encrypted-data",
            size_bytes=1024,
            content_type="image/jpeg",
            vault_id="vault-123",
        )

        assert request.encrypted_metadata == b"encrypted-data"
        assert request.size_bytes == 1024
        assert request.content_type == "image/jpeg"
        assert request.vault_id == "vault-123"
        assert request.encrypted_tags is None

    def test_with_encrypted_tags(self):
        """Should accept encrypted tags."""
        request = InitiateUploadRequest(
            encrypted_metadata=b"data",
            size_bytes=100,
            content_type="image/png",
            vault_id="vault-123",
            encrypted_tags=[b"tag1", b"tag2"],
        )

        assert request.encrypted_tags == [b"tag1", b"tag2"]

    def test_rejects_zero_size(self):
        """Should reject zero size_bytes."""
        with pytest.raises(PydanticValidationError):
            InitiateUploadRequest(
                encrypted_metadata=b"data",
                size_bytes=0,
                content_type="image/jpeg",
                vault_id="vault-123",
            )

    def test_rejects_negative_size(self):
        """Should reject negative size_bytes."""
        with pytest.raises(PydanticValidationError):
            InitiateUploadRequest(
                encrypted_metadata=b"data",
                size_bytes=-100,
                content_type="image/jpeg",
                vault_id="vault-123",
            )


class TestInitiateUploadResponse:
    """Tests for InitiateUploadResponse model."""

    def test_valid_response(self):
        """Should create valid response."""
        now = datetime.utcnow()
        response = InitiateUploadResponse(
            item_id="item-123",
            upload_url="https://s3.amazonaws.com/bucket/key",
            expires_at=now,
            s3_key="vaults/v1/files/f1/123",
        )

        assert response.item_id == "item-123"
        assert response.upload_url == "https://s3.amazonaws.com/bucket/key"
        assert response.expires_at == now
        assert response.s3_key == "vaults/v1/files/f1/123"
        assert response.upload_id is None

    def test_with_upload_id(self):
        """Should accept upload_id for multipart."""
        response = InitiateUploadResponse(
            item_id="item-123",
            upload_url="https://s3.amazonaws.com/bucket/key",
            expires_at=datetime.utcnow(),
            s3_key="key",
            upload_id="multipart-upload-id",
        )

        assert response.upload_id == "multipart-upload-id"


class TestListMediaRequest:
    """Tests for ListMediaRequest model."""

    def test_valid_request_with_defaults(self):
        """Should create request with defaults."""
        request = ListMediaRequest(vault_id="vault-123")

        assert request.vault_id == "vault-123"
        assert request.page_size == 50
        assert request.next_token is None
        assert request.sort_order == "desc"

    def test_custom_page_size(self):
        """Should accept custom page_size."""
        request = ListMediaRequest(vault_id="vault-123", page_size=25)

        assert request.page_size == 25

    def test_rejects_page_size_below_min(self):
        """Should reject page_size below 1."""
        with pytest.raises(PydanticValidationError):
            ListMediaRequest(vault_id="vault-123", page_size=0)

    def test_rejects_page_size_above_max(self):
        """Should reject page_size above 100."""
        with pytest.raises(PydanticValidationError):
            ListMediaRequest(vault_id="vault-123", page_size=101)

    def test_valid_sort_orders(self):
        """Should accept valid sort orders."""
        request_asc = ListMediaRequest(vault_id="v1", sort_order="asc")
        request_desc = ListMediaRequest(vault_id="v1", sort_order="desc")

        assert request_asc.sort_order == "asc"
        assert request_desc.sort_order == "desc"

    def test_rejects_invalid_sort_order(self):
        """Should reject invalid sort order."""
        with pytest.raises(PydanticValidationError):
            ListMediaRequest(vault_id="vault-123", sort_order="invalid")


class TestMediaItem:
    """Tests for MediaItem model."""

    def test_valid_item(self):
        """Should create valid media item."""
        now = datetime.utcnow()
        item = MediaItem(
            file_id="file-123",
            vault_id="vault-456",
            user_id="user-789",
            s3_key="vaults/v1/files/f1/key",
            encrypted_metadata=b"encrypted",
            uploaded_at=now,
            size_bytes=2048,
        )

        assert item.file_id == "file-123"
        assert item.vault_id == "vault-456"
        assert item.user_id == "user-789"
        assert item.s3_key == "vaults/v1/files/f1/key"
        assert item.encrypted_metadata == b"encrypted"
        assert item.uploaded_at == now
        assert item.size_bytes == 2048
        assert item.encrypted_tags is None


class TestCreateVaultRequest:
    """Tests for CreateVaultRequest model."""

    def test_valid_request(self):
        """Should create valid request with 16-byte salt."""
        salt = b"0123456789abcdef"  # 16 bytes
        request = CreateVaultRequest(vault_salt=salt)

        assert request.vault_salt == salt

    def test_rejects_short_salt(self):
        """Should reject salt shorter than 16 bytes."""
        with pytest.raises(PydanticValidationError):
            CreateVaultRequest(vault_salt=b"short")

    def test_rejects_long_salt(self):
        """Should reject salt longer than 16 bytes."""
        with pytest.raises(PydanticValidationError):
            CreateVaultRequest(vault_salt=b"0123456789abcdefg")  # 17 bytes


class TestCreateShareRequest:
    """Tests for CreateShareRequest model."""

    def test_valid_request_minimal(self):
        """Should create valid request with minimal fields."""
        request = CreateShareRequest(file_id="file-123", vault_id="vault-456")

        assert request.file_id == "file-123"
        assert request.vault_id == "vault-456"
        assert request.expires_at is None
        assert request.is_password_protected is False

    def test_with_expiration(self):
        """Should accept expiration timestamp."""
        expires = datetime.utcnow()
        request = CreateShareRequest(file_id="file-123", vault_id="vault-456", expires_at=expires)

        assert request.expires_at == expires

    def test_with_password_protection(self):
        """Should accept password protection flag."""
        request = CreateShareRequest(
            file_id="file-123", vault_id="vault-456", is_password_protected=True
        )

        assert request.is_password_protected is True


class TestDynamoDBFileItem:
    """Tests for DynamoDBFileItem model."""

    def test_valid_item(self):
        """Should create valid DynamoDB file item."""
        item = DynamoDBFileItem(
            PK="VAULT#vault-123",
            SK="FILE#file-456",
            file_id="file-456",
            vault_id="vault-123",
            user_id="user-789",
            s3_key="vaults/v1/files/f1/key",
            encrypted_metadata=b"encrypted",
            uploaded_at=1234567890,
            size_bytes=1024,
        )

        assert item.PK == "VAULT#vault-123"
        assert item.SK == "FILE#file-456"
        assert item.file_id == "file-456"
        assert item.GSI1PK is None
        assert item.GSI1SK is None

    def test_with_gsi_keys(self):
        """Should accept GSI keys."""
        item = DynamoDBFileItem(
            PK="VAULT#vault-123",
            SK="FILE#file-456",
            file_id="file-456",
            vault_id="vault-123",
            user_id="user-789",
            s3_key="key",
            encrypted_metadata=b"data",
            uploaded_at=1234567890,
            size_bytes=100,
            GSI1PK="VAULT#vault-123#TAG#encrypted-tag",
            GSI1SK="FILE#file-456",
        )

        assert item.GSI1PK == "VAULT#vault-123#TAG#encrypted-tag"
        assert item.GSI1SK == "FILE#file-456"


class TestDynamoDBVaultItem:
    """Tests for DynamoDBVaultItem model."""

    def test_valid_item(self):
        """Should create valid DynamoDB vault item."""
        item = DynamoDBVaultItem(
            PK="USER#user-123",
            SK="VAULT#vault-456",
            vault_id="vault-456",
            user_id="user-123",
            vault_salt=b"0123456789abcdef",
            created_at=1234567890,
        )

        assert item.PK == "USER#user-123"
        assert item.SK == "VAULT#vault-456"
        assert item.vault_id == "vault-456"
        assert item.vault_salt == b"0123456789abcdef"


class TestDynamoDBShareItem:
    """Tests for DynamoDBShareItem model."""

    def test_valid_item_minimal(self):
        """Should create valid share item with minimal fields."""
        item = DynamoDBShareItem(
            PK="SHARE#share-123",
            SK="METADATA",
            share_id="share-123",
            file_id="file-456",
            vault_id="vault-789",
            user_id="user-abc",
            created_at=1234567890,
        )

        assert item.PK == "SHARE#share-123"
        assert item.SK == "METADATA"
        assert item.is_password_protected is False
        assert item.is_revoked is False
        assert item.access_count == 0
        assert item.expires_at is None
        assert item.last_accessed_at is None

    def test_with_all_fields(self):
        """Should accept all optional fields."""
        item = DynamoDBShareItem(
            PK="SHARE#share-123",
            SK="METADATA",
            share_id="share-123",
            file_id="file-456",
            vault_id="vault-789",
            user_id="user-abc",
            created_at=1234567890,
            expires_at=1234567900,
            is_password_protected=True,
            is_revoked=True,
            access_count=5,
            last_accessed_at=1234567895,
        )

        assert item.expires_at == 1234567900
        assert item.is_password_protected is True
        assert item.is_revoked is True
        assert item.access_count == 5
        assert item.last_accessed_at == 1234567895


class TestDynamoDBRecoveryCodeItem:
    """Tests for DynamoDBRecoveryCodeItem model."""

    def test_valid_item(self):
        """Should create valid recovery code item."""
        item = DynamoDBRecoveryCodeItem(
            PK="USER#user-123",
            SK="RECOVERY#hash-abc",
            user_id="user-123",
            code_hash="hash-abc",
            created_at=1234567890,
        )

        assert item.PK == "USER#user-123"
        assert item.SK == "RECOVERY#hash-abc"
        assert item.is_valid is True
        assert item.used_at is None

    def test_used_code(self):
        """Should track used code."""
        item = DynamoDBRecoveryCodeItem(
            PK="USER#user-123",
            SK="RECOVERY#hash-abc",
            user_id="user-123",
            code_hash="hash-abc",
            created_at=1234567890,
            used_at=1234567900,
            is_valid=False,
        )

        assert item.used_at == 1234567900
        assert item.is_valid is False


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_valid_response(self):
        """Should create valid error response."""
        response = ErrorResponse(
            error={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Authentication required",
                "requestId": "req-123",
                "timestamp": "2024-01-01T00:00:00Z",
            }
        )

        assert response.error["code"] == "AUTHENTICATION_REQUIRED"
        assert response.error["message"] == "Authentication required"


class TestCompleteUploadRequest:
    """Tests for CompleteUploadRequest model."""

    def test_valid_request(self):
        """Should create valid request."""
        request = CompleteUploadRequest(item_id="item-123", vault_id="vault-456")

        assert request.item_id == "item-123"
        assert request.vault_id == "vault-456"


class TestCreateCollectionRequest:
    """Tests for CreateCollectionRequest model."""

    def test_valid_request(self):
        """Should create valid request."""
        request = CreateCollectionRequest(
            vault_id="vault-123", encrypted_metadata=b"encrypted-name"
        )

        assert request.vault_id == "vault-123"
        assert request.encrypted_metadata == b"encrypted-name"


class TestCollectionItem:
    """Tests for CollectionItem model."""

    def test_valid_item(self):
        """Should create valid collection item."""
        now = datetime.utcnow()
        item = CollectionItem(
            collection_id="col-123",
            vault_id="vault-456",
            user_id="user-789",
            encrypted_metadata=b"encrypted",
            created_at=now,
            updated_at=now,
        )

        assert item.collection_id == "col-123"
        assert item.item_count == 0

    def test_with_item_count(self):
        """Should accept item count."""
        now = datetime.utcnow()
        item = CollectionItem(
            collection_id="col-123",
            vault_id="vault-456",
            user_id="user-789",
            encrypted_metadata=b"encrypted",
            created_at=now,
            updated_at=now,
            item_count=10,
        )

        assert item.item_count == 10


class TestSearchByTagRequest:
    """Tests for SearchByTagRequest model."""

    def test_valid_request(self):
        """Should create valid request."""
        request = SearchByTagRequest(vault_id="vault-123", encrypted_tag=b"encrypted-tag")

        assert request.vault_id == "vault-123"
        assert request.encrypted_tag == b"encrypted-tag"
        assert request.page_size == 50
        assert request.next_token is None


class TestGenerateRecoveryCodesResponse:
    """Tests for GenerateRecoveryCodesResponse model."""

    def test_valid_response(self):
        """Should create valid response."""
        now = datetime.utcnow()
        response = GenerateRecoveryCodesResponse(
            recovery_codes=["CODE-1", "CODE-2", "CODE-3"], generated_at=now
        )

        assert len(response.recovery_codes) == 3
        assert response.generated_at == now


class TestValidateRecoveryCodeRequest:
    """Tests for ValidateRecoveryCodeRequest model."""

    def test_valid_request(self):
        """Should create valid request."""
        request = ValidateRecoveryCodeRequest(
            user_id="user-123", recovery_code="XXXX-XXXX-XXXX-XXXX"
        )

        assert request.user_id == "user-123"
        assert request.recovery_code == "XXXX-XXXX-XXXX-XXXX"
