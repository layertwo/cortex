"""
Unit tests for Pydantic ValidationError handling in routes.

Tests verify that Pydantic validation errors are properly caught and
return sanitized error responses without exposing internal error structure.
"""

import json

from src.entrypoint.api import lambda_handler


class TestPydanticValidationErrorHandling:
    """Test suite for Pydantic ValidationError handling."""

    def test_create_item_invalid_base64(self, mock_service_provider):
        """Test that invalid base64 in CreateItemRequest returns sanitized error."""
        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_id": "vault-123",
                    "item_type": "NOTE",
                    "encrypted_content": 12345,  # Invalid type (should be string)
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 with sanitized error message
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert body["message"] == "Invalid request format"
        # Should NOT expose Pydantic's internal error structure
        assert "validation_error" not in body["message"].lower()

    def test_create_item_missing_required_field(self, mock_service_provider):
        """Test that missing required field returns sanitized error."""
        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_id": "vault-123",
                    # Missing item_type, encrypted_content, encrypted_metadata
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 with sanitized error message
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert body["message"] == "Invalid request format"

    def test_initiate_upload_invalid_size(self, mock_service_provider):
        """Test that invalid size_bytes type returns sanitized error."""
        event = {
            "resource": "/v1/items/upload/init",
            "path": "/v1/items/upload/init",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_id": "vault-123",
                    "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
                    "size_bytes": "not-a-number",  # Invalid type
                    "content_type": "image/jpeg",
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 with sanitized error message
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert body["message"] == "Invalid request format"

    def test_create_vault_invalid_salt(self, mock_service_provider):
        """Test that invalid vault_salt returns sanitized error."""
        event = {
            "resource": "/v1/vaults",
            "path": "/v1/vaults",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "vault_salt": "invalid-base64!!!",  # Invalid base64
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 with sanitized error message
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert body["message"] == "Invalid request format"

    def test_login_missing_password(self, mock_service_provider):
        """Test that missing password in login returns sanitized error."""
        event = {
            "resource": "/v1/auth/login",
            "path": "/v1/auth/login",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "email": "test@example.com",
                    # Missing password
                }
            ),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 with sanitized error message
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert body["message"] == "Invalid request format"

    def test_validate_recovery_code_missing_code(self, mock_service_provider):
        """Test that missing recovery_code returns sanitized error."""
        event = {
            "resource": "/v1/recovery/validate",
            "path": "/v1/recovery/validate",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {
                    # Missing recovery_code
                }
            ),
            "requestContext": {
                "requestId": "test-request-id",
                "authorizer": {"claims": {"sub": "test-user-123"}},
            },
        }

        response = lambda_handler(event, {}, mock_service_provider)

        # Should return 400 with sanitized error message
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert body["message"] == "Invalid request format"
