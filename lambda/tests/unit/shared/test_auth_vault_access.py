"""
Unit tests for vault authorization helper function.

Tests verify that require_vault_access properly enforces vault ownership
and prevents OWASP A01:2021 - Broken Access Control vulnerabilities.
"""

from unittest.mock import MagicMock

import pytest

from src.shared.auth import require_vault_access
from src.shared.errors import AuthorizationError


class TestRequireVaultAccess:
    """Test suite for require_vault_access function."""

    def test_require_vault_access_allows_owner(self):
        """Test that vault owner is allowed access."""
        # Mock vault service that returns True (user owns vault)
        mock_vault_service = MagicMock()
        mock_vault_service.vault_exists.return_value = True

        user_id = "user-123"
        vault_id = "vault-456"

        # Should not raise exception
        require_vault_access(mock_vault_service, user_id, vault_id, "test_operation")

        # Verify vault_exists was called with correct parameters
        mock_vault_service.vault_exists.assert_called_once_with(user_id, vault_id)

    def test_require_vault_access_denies_non_owner(self):
        """
        Test that non-owner is denied access.

        Security: CRITICAL - Prevents OWASP A01:2021 - Broken Access Control
        """
        # Mock vault service that returns False (user doesn't own vault)
        mock_vault_service = MagicMock()
        mock_vault_service.vault_exists.return_value = False

        user_id = "user-123"
        vault_id = "vault-456"

        # Should raise AuthorizationError
        with pytest.raises(AuthorizationError) as exc_info:
            require_vault_access(mock_vault_service, user_id, vault_id, "test_operation")

        # Verify error message
        assert "Access denied to vault" in str(exc_info.value)

        # Verify vault_exists was called
        mock_vault_service.vault_exists.assert_called_once_with(user_id, vault_id)

    def test_require_vault_access_with_different_operations(self):
        """Test that operation name is used for logging."""
        mock_vault_service = MagicMock()
        mock_vault_service.vault_exists.return_value = True

        user_id = "user-123"
        vault_id = "vault-456"

        # Test with different operation names
        operations = ["delete_item", "list_items", "get_item", "download_item"]

        for operation in operations:
            require_vault_access(mock_vault_service, user_id, vault_id, operation)

        # Verify vault_exists was called for each operation
        assert mock_vault_service.vault_exists.call_count == len(operations)

    def test_require_vault_access_with_multiple_users(self):
        """Test that different users are checked independently."""
        mock_vault_service = MagicMock()

        # User 1 owns vault-1
        mock_vault_service.vault_exists.side_effect = lambda uid, vid: (
            uid == "user-1" and vid == "vault-1"
        )

        # User 1 can access vault-1
        require_vault_access(mock_vault_service, "user-1", "vault-1", "test")

        # User 2 cannot access vault-1
        with pytest.raises(AuthorizationError):
            require_vault_access(mock_vault_service, "user-2", "vault-1", "test")

        # User 1 cannot access vault-2
        with pytest.raises(AuthorizationError):
            require_vault_access(mock_vault_service, "user-1", "vault-2", "test")

    def test_require_vault_access_default_operation_name(self):
        """Test that default operation name is used when not specified."""
        mock_vault_service = MagicMock()
        mock_vault_service.vault_exists.return_value = True

        user_id = "user-123"
        vault_id = "vault-456"

        # Call without operation parameter (uses default "access")
        require_vault_access(mock_vault_service, user_id, vault_id)

        # Verify vault_exists was called
        mock_vault_service.vault_exists.assert_called_once_with(user_id, vault_id)
