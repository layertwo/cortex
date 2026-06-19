"""
Unit tests for Pydantic ValidationError handling in routes.

Tests verify that Pydantic validation errors are properly caught and
return appropriate error responses. FastAPI returns 422 for validation errors.
"""


class TestPydanticValidationErrorHandling:
    """Test suite for Pydantic ValidationError handling."""

    def test_create_item_invalid_base64(self, client):
        """Test that invalid base64 in CreateItemRequest returns validation error."""
        response = client.post(
            "/v1/items",
            json={
                "vault_id": "vault-123",
                "item_type": "NOTE",
                "encrypted_content": 12345,  # Invalid type (should be string)
                "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
            },
        )

        # FastAPI returns 422 for Pydantic validation errors
        assert response.status_code == 422

    def test_create_item_missing_required_field(self, client):
        """Test that missing required field returns validation error."""
        response = client.post(
            "/v1/items",
            json={
                "vault_id": "vault-123",
                # Missing item_type, encrypted_content, encrypted_metadata
            },
        )

        assert response.status_code == 422

    def test_initiate_upload_invalid_size(self, client):
        """Test that invalid size_bytes type returns validation error."""
        response = client.post(
            "/v1/items/upload/init",
            json={
                "vault_id": "vault-123",
                "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                "size_bytes": "not-a-number",  # Invalid type
                "content_type": "image/jpeg",
            },
        )

        assert response.status_code == 422

    def test_create_vault_invalid_salt(self, client):
        """Test that invalid vault_salt returns validation error."""
        response = client.post(
            "/v1/vaults",
            json={
                "vault_salt": "invalid-base64!!!",  # Invalid base64
            },
        )

        assert response.status_code == 422
