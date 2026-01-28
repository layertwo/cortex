"""
Unit tests for shared/models.py module.

Tests Pydantic models for request/response validation.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.shared.models import (
    CollectionItem,
    CompleteUploadRequest,
    CreateCollectionRequest,
    CreateItemRequest,
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

    def test_valid_response(self, now):
        """Should create valid response."""
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

    def test_with_upload_id(self, now):
        """Should accept upload_id for multipart."""
        response = InitiateUploadResponse(
            item_id="item-123",
            upload_url="https://s3.amazonaws.com/bucket/key",
            expires_at=now,
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

    def test_valid_item(self, now):
        """Should create valid media item."""
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

    def test_with_expiration(self, now):
        """Should accept expiration timestamp."""
        request = CreateShareRequest(file_id="file-123", vault_id="vault-456", expires_at=now)

        assert request.expires_at == now

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

    def test_valid_item(self, now):
        """Should create valid collection item."""
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

    def test_with_item_count(self, now):
        """Should accept item count."""
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

    def test_valid_response(self, now):
        """Should create valid response."""
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


class TestListMediaRequestValidators:
    """Tests for ListMediaRequest validators."""

    def test_invalid_sort_order(self):
        """Should reject invalid sort_order."""
        with pytest.raises(PydanticValidationError) as exc_info:
            ListMediaRequest(vault_id="vault-123", sort_order="invalid")

        assert "sort_order must be 'asc' or 'desc'" in str(exc_info.value)

    def test_valid_sort_order_asc(self):
        """Should accept 'asc' sort_order."""
        request = ListMediaRequest(vault_id="vault-123", sort_order="asc")
        assert request.sort_order == "asc"

    def test_valid_sort_order_desc(self):
        """Should accept 'desc' sort_order."""
        request = ListMediaRequest(vault_id="vault-123", sort_order="desc")
        assert request.sort_order == "desc"

    def test_default_values(self):
        """Should use default values when not specified."""
        request = ListMediaRequest(vault_id="vault-123")
        assert request.sort_order == "desc"
        assert request.page_size == 50
        assert request.next_token is None


class TestCreateItemRequest:
    """Tests for CreateItemRequest model."""

    def test_valid_request_with_all_fields(self):
        """Should create valid request with all fields."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type="NOTE",
            encrypted_content=b"encrypted-note-content",
            encrypted_metadata=b"encrypted-metadata",
            encrypted_tags=[b"tag1", b"tag2"],
        )

        assert request.vault_id == "vault-123"
        assert request.item_type == "NOTE"
        assert request.encrypted_content == b"encrypted-note-content"
        assert request.encrypted_metadata == b"encrypted-metadata"
        assert request.encrypted_tags == [b"tag1", b"tag2"]


class TestCreateItemRequestValidation:
    """Tests for CreateItemRequest validation."""

    def test_create_item_with_minimal_fields(self):
        """Should create item with minimal required fields."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type="NOTE",
            encrypted_content=b"content",
            encrypted_metadata=b"metadata",
        )

        assert request.vault_id == "vault-123"
        assert request.item_type == "NOTE"
        assert request.encrypted_content == b"content"
        assert request.encrypted_metadata == b"metadata"
        assert request.encrypted_tags is None

    def test_create_item_with_empty_tags_list(self):
        """Should accept empty tags list."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type="TASK",
            encrypted_content=b"task-content",
            encrypted_metadata=b"metadata",
            encrypted_tags=[],
        )

        assert request.encrypted_tags == []


class TestListItemsRequestValidators:
    """Tests for ListItemsRequest validators."""

    def test_item_type_none_passes_validation(self):
        """Should accept None for item_type (covers the v is None branch)."""
        from src.shared.models import ListItemsRequest

        request = ListItemsRequest(vault_id="vault-123", item_type=None)
        assert request.item_type is None

    def test_item_type_valid_media(self):
        """Should accept valid MEDIA item_type."""
        from src.shared.models import ItemType, ListItemsRequest

        request = ListItemsRequest(vault_id="vault-123", item_type=ItemType.MEDIA)
        assert request.item_type == ItemType.MEDIA

    def test_item_type_valid_note(self):
        """Should accept valid NOTE item_type."""
        from src.shared.models import ItemType, ListItemsRequest

        request = ListItemsRequest(vault_id="vault-123", item_type=ItemType.NOTE)
        assert request.item_type == ItemType.NOTE

    def test_item_type_valid_task(self):
        """Should accept valid TASK item_type."""
        from src.shared.models import ItemType, ListItemsRequest

        request = ListItemsRequest(vault_id="vault-123", item_type=ItemType.TASK)
        assert request.item_type == ItemType.TASK

    def test_item_type_valid_event(self):
        """Should accept valid EVENT item_type."""
        from src.shared.models import ItemType, ListItemsRequest

        request = ListItemsRequest(vault_id="vault-123", item_type=ItemType.EVENT)
        assert request.item_type == ItemType.EVENT


class TestCompleteUploadRequestValidation:
    """Tests for CompleteUploadRequest validation."""

    def test_complete_upload_with_required_fields(self):
        """Should create request with required fields."""
        request = CompleteUploadRequest(item_id="item-123", vault_id="vault-123")

        assert request.item_id == "item-123"
        assert request.vault_id == "vault-123"


class TestCreateItemRequestItemTypeValidation:
    """Tests for CreateItemRequest item_type validation."""

    def test_create_item_invalid_item_type_media(self):
        """Should reject MEDIA type for inline content (CreateItemRequest)."""
        with pytest.raises(PydanticValidationError) as exc_info:
            CreateItemRequest(
                vault_id="vault-123",
                item_type="MEDIA",
                encrypted_content=b"content",
                encrypted_metadata=b"metadata",
            )

        assert "item_type must be NOTE, TASK, or EVENT" in str(exc_info.value)

    def test_create_item_valid_note_type(self):
        """Should accept NOTE type."""
        request = CreateItemRequest(
            vault_id="vault-123",
            item_type="NOTE",
            encrypted_content=b"content",
            encrypted_metadata=b"metadata",
        )
        assert request.item_type == "NOTE"
