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


class TestGenerateRecoveryCodes:
    def test_generate_recovery_codes_success(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        codes, timestamp = service.generate_recovery_codes("user-123")
        assert len(codes) == RECOVERY_CODE_COUNT
        assert timestamp > 0

    def test_generate_recovery_codes_stores_hashed(self):
        mock_table = MagicMock()
        service = AuthService(recovery_table=mock_table)
        service.generate_recovery_codes("user-123")
        assert mock_table.put_item.call_count == RECOVERY_CODE_COUNT


class TestValidateRecoveryCode:
    def test_validate_recovery_code_success(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": {"is_valid": True, "code_hash": "somehash"}}
        service = AuthService(recovery_table=mock_table)
        result = service.validate_recovery_code("user-123", "ABCD-EFGH-IJKL-MNOP")
        assert result is True

    def test_validate_recovery_code_not_found(self):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        service = AuthService(recovery_table=mock_table)
        with pytest.raises(RecoveryCodeInvalidError):
            service.validate_recovery_code("user-123", "ABCD-EFGH-IJKL-MNOP")
