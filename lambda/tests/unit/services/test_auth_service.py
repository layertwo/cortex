"""Unit tests for authentication service layer."""

from unittest.mock import MagicMock

import pytest

from src.api.services.auth_service import RECOVERY_CODE_COUNT, AuthService
from src.shared.errors import RecoveryCodeInvalidError, ValidationError


class TestAuthServiceInit:
    def test_init_with_recovery_table(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        assert service.recovery_table == mock_table

    def test_init_with_all_params(self):
        mock_table = MagicMock()
        mock_cognito = MagicMock()
        service = AuthService(
            recovery_table=mock_table, cognito_client=mock_cognito, user_pool_id="test-pool-id"
        )
        assert service.cognito_client == mock_cognito


class TestValidateLogin:
    def test_validate_login_success(self):
        service = AuthService(recovery_table=MagicMock())
        result = service.validate_login("test@example.com", "password123")
        assert result["auth_type"] == "cognito"

    def test_validate_login_empty_email(self):
        service = AuthService(recovery_table=MagicMock())
        with pytest.raises(ValidationError):
            service.validate_login("", "password123")


class TestRefreshToken:
    def test_refresh_token_success(self):
        service = AuthService(recovery_table=MagicMock())
        result = service.refresh_token("test-refresh-token")
        assert result["auth_type"] == "cognito"

    def test_refresh_token_empty(self):
        service = AuthService(recovery_table=MagicMock())
        with pytest.raises(ValidationError, match="Refresh token is required"):
            service.refresh_token("")


class TestGenerateRecoveryCodes:
    def test_generate_recovery_codes_success(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        codes, timestamp = service.generate_recovery_codes("user-123")
        assert len(codes) == RECOVERY_CODE_COUNT

    def test_generate_recovery_codes_empty_user_id(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(ValidationError, match="User ID is required"):
            service.generate_recovery_codes("")

    def test_generate_recovery_codes_stores_hashed(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        service.generate_recovery_codes("user-123")
        assert mock_table.put_item.call_count == RECOVERY_CODE_COUNT


class TestValidateRecoveryCode:
    def test_validate_recovery_code_success(self):
        import hashlib

        mock_table = MagicMock()
        # Compute the correct hash for the test code
        test_code = "ABCDEFGHIJKLMNOP"
        code_hash = hashlib.sha256(test_code.encode("utf-8")).hexdigest()
        mock_table.get_item.return_value = {"Item": {"is_valid": True, "code_hash": code_hash}}
        service = AuthService(recovery_table=mock_table)
        result = service.validate_recovery_code("user-123", "ABCD-EFGH-IJKL-MNOP")
        assert result is True

    def test_validate_recovery_code_not_found(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(RecoveryCodeInvalidError):
            service.validate_recovery_code("user-123", "ABCD-EFGH-IJKL-MNOP")


class TestValidateRecoveryCodeEdgeCases:
    """Test edge cases in recovery code validation."""

    def test_validate_recovery_code_hash_mismatch(self):
        """Test recovery code with hash mismatch."""
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)

        # Mock get_item to return code with wrong hash
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "USER#user-123",
                "SK": "RECOVERY#wronghash",
                "code_hash": "wronghash",
                "is_valid": True,
            }
        }

        with pytest.raises(RecoveryCodeInvalidError):
            service.validate_recovery_code("user-123", "AAAA-BBBB-CCCC-DDDD")

    def test_validate_recovery_code_already_used(self):
        """Test recovery code that was already used."""
        import hashlib

        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)

        code = "AAAA-BBBB-CCCC-DDDD"
        normalized = code.replace("-", "").upper()
        code_hash = hashlib.sha256(normalized.encode()).hexdigest()

        # Mock get_item to return used code
        mock_table.get_item.return_value = {
            "Item": {
                "PK": "USER#user-123",
                "SK": f"RECOVERY#{code_hash}",
                "code_hash": code_hash,
                "is_valid": False,  # Already used
            }
        }

        with pytest.raises(RecoveryCodeInvalidError, match="already been used"):
            service.validate_recovery_code("user-123", code)


class TestValidateRecoveryCodeValidation:
    """Test validation in validate_recovery_code."""

    def test_validate_recovery_code_empty_user_id(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(ValidationError, match="User ID and recovery code are required"):
            service.validate_recovery_code("", "AAAA-BBBB-CCCC-DDDD")

    def test_validate_recovery_code_empty_code(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(ValidationError, match="User ID and recovery code are required"):
            service.validate_recovery_code("user-123", "")


class TestInitiateRecoveryValidation:
    """Test validation in initiate_recovery."""

    def test_initiate_recovery_empty_email(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(ValidationError, match="Email and recovery code are required"):
            service.initiate_recovery("", "AAAA-BBBB-CCCC-DDDD")

    def test_initiate_recovery_empty_code(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(ValidationError, match="Email and recovery code are required"):
            service.initiate_recovery("test@example.com", "")


class TestValidateLoginValidation:
    """Test validation in validate_login."""

    def test_validate_login_empty_password(self):
        service = AuthService(recovery_table=MagicMock())
        with pytest.raises(ValidationError):
            service.validate_login("test@example.com", "")


class TestInitiateRecoveryFlow:
    """Test initiate_recovery flow."""

    def test_initiate_recovery_normalizes_code(self):
        """Test that recovery code is normalized during initiate_recovery."""
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)

        # Call initiate_recovery with formatted code
        result = service.initiate_recovery("test@example.com", "AAAA-BBBB-CCCC-DDDD")

        # Should return placeholder response
        assert result["recovery_type"] == "account_password"


class TestValidateRecoveryCodeExceptionHandling:
    """Test exception handling in validate_recovery_code."""

    def test_validate_recovery_code_generic_exception(self):
        """Test generic exception handling in validate_recovery_code."""
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)

        # Mock get_item to raise a generic exception
        mock_table.get_item.side_effect = Exception("Database error")

        with pytest.raises(RecoveryCodeInvalidError):
            service.validate_recovery_code("user-123", "AAAA-BBBB-CCCC-DDDD")


class TestValidateLoginEdgeCases:
    """Test edge cases in validate_login."""

    def test_validate_login_empty_email(self):
        """Test validation with empty email."""
        service = AuthService(recovery_table=MagicMock())
        with pytest.raises(ValidationError, match="Email and password are required"):
            service.validate_login("", "password123")

    def test_validate_login_both_empty(self):
        """Test validation with both fields empty."""
        service = AuthService(recovery_table=MagicMock())
        with pytest.raises(ValidationError, match="Email and password are required"):
            service.validate_login("", "")
