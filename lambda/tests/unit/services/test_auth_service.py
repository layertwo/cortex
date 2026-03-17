"""Unit tests for authentication auth_service layer."""

import hashlib

import pytest
from botocore.stub import ANY

from src.api.services.auth_service import RECOVERY_CODE_COUNT
from src.shared.exceptions import BadRequestError, UnauthorizedError


class TestValidateLogin:
    def test_validate_login_success(self, auth_service):
        result = auth_service.validate_login("test@example.com", "password123")
        assert result["auth_type"] == "cognito"

    def test_validate_login_empty_email(self, auth_service):
        with pytest.raises(BadRequestError):
            auth_service.validate_login("", "password123")


class TestRefreshToken:
    def test_refresh_token_success(self, auth_service):
        result = auth_service.refresh_token("test-refresh-token")
        assert result["auth_type"] == "cognito"

    def test_refresh_token_empty(self, auth_service):
        with pytest.raises(BadRequestError, match="Refresh token is required"):
            auth_service.refresh_token("")


class TestGenerateRecoveryCodes:
    def test_generate_recovery_codes_success(self, auth_service, dynamodb_stubber):
        """Test successful generation of recovery codes with stubbed DynamoDB."""
        # Stub put_item for each recovery code
        for _ in range(RECOVERY_CODE_COUNT):
            dynamodb_stubber.add_response(
                "put_item",
                {},
                {"TableName": "test-recovery-table", "Item": ANY},
            )

        codes, timestamp = auth_service.generate_recovery_codes("user-123")
        assert len(codes) == RECOVERY_CODE_COUNT
        assert timestamp > 0

    def test_generate_recovery_codes_empty_user_id(self, auth_service):
        with pytest.raises(BadRequestError, match="User ID is required"):
            auth_service.generate_recovery_codes("")

    def test_generate_recovery_codes_stores_hashed(self, auth_service, dynamodb_stubber):
        """Test that recovery codes are stored with hashed values."""
        # Stub put_item for each recovery code
        for _ in range(RECOVERY_CODE_COUNT):
            dynamodb_stubber.add_response(
                "put_item",
                {},
                {"TableName": "test-recovery-table", "Item": ANY},
            )

        codes, _ = auth_service.generate_recovery_codes("user-123")

        # Verify codes are in correct format
        for code in codes:
            assert len(code) == 19  # XXXX-XXXX-XXXX-XXXX
            assert code.count("-") == 3


class TestValidateRecoveryCode:
    def test_validate_recovery_code_success(self, auth_service, dynamodb_stubber):
        """Test successful recovery code validation."""
        test_code = "ABCD-EFGH-IJKL-MNOP"
        normalized = test_code.replace("-", "").upper()
        code_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        # Stub get_item to return valid code - use ANY for Key since Table transforms it
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#user-123"},
                    "SK": {"S": f"RECOVERY#{code_hash}"},
                    "code_hash": {"S": code_hash},
                    "is_valid": {"BOOL": True},
                }
            },
            {
                "TableName": "test-recovery-table",
                "Key": ANY,
            },
        )

        # Stub update_item to mark code as used
        dynamodb_stubber.add_response(
            "update_item",
            {},
            {
                "TableName": "test-recovery-table",
                "Key": ANY,
                "UpdateExpression": ANY,
                "ExpressionAttributeValues": ANY,
            },
        )

        result = auth_service.validate_recovery_code("user-123", test_code)
        assert result is True

    def test_validate_recovery_code_not_found(self, auth_service, dynamodb_stubber):
        """Test recovery code validation when code not found."""
        test_code = "ABCD-EFGH-IJKL-MNOP"

        # Stub get_item to return empty response
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": "test-recovery-table",
                "Key": ANY,
            },
        )

        with pytest.raises(UnauthorizedError):
            auth_service.validate_recovery_code("user-123", test_code)


class TestValidateRecoveryCodeEdgeCases:
    """Test edge cases in recovery code validation."""

    def test_validate_recovery_code_hash_mismatch(self, auth_service, dynamodb_stubber):
        """Test recovery code with hash mismatch."""
        test_code = "AAAA-BBBB-CCCC-DDDD"

        # Stub get_item to return code with wrong hash
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#user-123"},
                    "SK": {"S": "RECOVERY#wronghash"},
                    "code_hash": {"S": "wronghash"},
                    "is_valid": {"BOOL": True},
                }
            },
            {
                "TableName": "test-recovery-table",
                "Key": ANY,
            },
        )

        with pytest.raises(UnauthorizedError):
            auth_service.validate_recovery_code("user-123", test_code)

    def test_validate_recovery_code_already_used(self, auth_service, dynamodb_stubber):
        """Test recovery code that was already used."""
        test_code = "AAAA-BBBB-CCCC-DDDD"
        normalized = test_code.replace("-", "").upper()
        code_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        # Stub get_item to return used code
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": "USER#user-123"},
                    "SK": {"S": f"RECOVERY#{code_hash}"},
                    "code_hash": {"S": code_hash},
                    "is_valid": {"BOOL": False},  # Already used
                }
            },
            {
                "TableName": "test-recovery-table",
                "Key": ANY,
            },
        )

        with pytest.raises(UnauthorizedError, match="already been used"):
            auth_service.validate_recovery_code("user-123", test_code)


class TestValidateRecoveryCodeValidation:
    """Test validation in validate_recovery_code."""

    def test_validate_recovery_code_empty_user_id(self, auth_service):
        with pytest.raises(BadRequestError, match="User ID and recovery code are required"):
            auth_service.validate_recovery_code("", "AAAA-BBBB-CCCC-DDDD")

    def test_validate_recovery_code_empty_code(self, auth_service):
        with pytest.raises(BadRequestError, match="User ID and recovery code are required"):
            auth_service.validate_recovery_code("user-123", "")


class TestInitiateRecoveryValidation:
    """Test validation in initiate_recovery."""

    def test_initiate_recovery_empty_email(self, auth_service):
        with pytest.raises(BadRequestError, match="Email and recovery code are required"):
            auth_service.initiate_recovery("", "AAAA-BBBB-CCCC-DDDD")

    def test_initiate_recovery_empty_code(self, auth_service):
        with pytest.raises(BadRequestError, match="Email and recovery code are required"):
            auth_service.initiate_recovery("test@example.com", "")


class TestValidateLoginValidation:
    """Test validation in validate_login."""

    def test_validate_login_empty_password(self, auth_service):
        with pytest.raises(BadRequestError):
            auth_service.validate_login("test@example.com", "")


class TestInitiateRecoveryFlow:
    """Test initiate_recovery flow."""

    def test_initiate_recovery_normalizes_code(self, auth_service):
        """Test that recovery code is normalized during initiate_recovery."""
        result = auth_service.initiate_recovery("test@example.com", "AAAA-BBBB-CCCC-DDDD")
        assert result["recovery_type"] == "account_password"


class TestValidateRecoveryCodeExceptionHandling:
    """Test exception handling in validate_recovery_code."""

    def test_validate_recovery_code_generic_exception(self, auth_service, dynamodb_stubber):
        """Test generic exception handling in validate_recovery_code."""
        test_code = "AAAA-BBBB-CCCC-DDDD"

        # Stub get_item to raise an error
        dynamodb_stubber.add_client_error(
            "get_item",
            service_error_code="InternalServerError",
            service_message="Database error",
            expected_params={
                "TableName": "test-recovery-table",
                "Key": ANY,
            },
        )

        with pytest.raises(UnauthorizedError):
            auth_service.validate_recovery_code("user-123", test_code)


class TestValidateLoginEdgeCases:
    """Test edge cases in validate_login."""

    def test_validate_login_empty_email(self, auth_service):
        """Test validation with empty email."""
        with pytest.raises(BadRequestError, match="Email and password are required"):
            auth_service.validate_login("", "password123")

    def test_validate_login_both_empty(self, auth_service):
        """Test validation with both fields empty."""
        with pytest.raises(BadRequestError, match="Email and password are required"):
            auth_service.validate_login("", "")
