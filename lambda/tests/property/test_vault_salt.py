"""
Property-Based Tests for Vault Salt Uniqueness.

Feature: cortex, Property 27: Vault salt uniqueness

For any two distinct vaults, their vault salts must differ, so the same vault
password derives different vault master keys per vault.

Validates: Requirements 22.4

These exercise the REAL VaultService.create_vault (which generates the salt via
secrets.token_bytes) against a botocore-stubbed DynamoDB, rather than a toy
in-test registry.
"""

import pytest
from botocore.stub import ANY

from src.shared.exceptions import BadRequestError

VAULTS_TABLE = "test-vaults-table"


def _stub_put(dynamodb_stubber, n=1):
    """Queue `n` successful vault put_item responses (create_vault writes one each)."""
    for _ in range(n):
        dynamodb_stubber.add_response(
            "put_item", {}, {"TableName": VAULTS_TABLE, "Item": ANY, "ConditionExpression": ANY}
        )


class TestVaultSaltUniqueness:
    """Property 27: real VaultService salt generation and uniqueness."""

    def test_create_vault_generates_16_byte_salt(self, vault_service, dynamodb_stubber):
        _stub_put(dynamodb_stubber)
        result = vault_service.create_vault("user-1")

        assert isinstance(result["vault_salt"], bytes)
        assert len(result["vault_salt"]) == 16
        assert result["vault_id"]

    def test_distinct_vaults_get_distinct_salts(self, vault_service, dynamodb_stubber):
        """For any two vaults created with no salt supplied, the generated salts differ."""
        _stub_put(dynamodb_stubber, n=3)
        salts = {vault_service.create_vault(f"user-{i}")["vault_salt"] for i in range(3)}

        # 3 independent CSPRNG draws -> 3 distinct salts (collision prob ~2^-128).
        assert len(salts) == 3
        dynamodb_stubber.assert_no_pending_responses()

    def test_provided_salt_must_be_16_bytes(self, vault_service, dynamodb_stubber):
        """An invalid client-supplied salt is rejected before any storage write."""
        # No put_item is queued: validation must raise before reaching DynamoDB.
        with pytest.raises(BadRequestError, match="16 bytes"):
            vault_service.create_vault("user-1", vault_salt=b"too-short")

    def test_provided_valid_salt_is_stored_and_returned(self, vault_service, dynamodb_stubber):
        """A valid 16-byte client salt is accepted and returned verbatim."""
        _stub_put(dynamodb_stubber)
        salt = bytes(range(16))
        result = vault_service.create_vault("user-1", vault_salt=salt)

        assert result["vault_salt"] == salt
        dynamodb_stubber.assert_no_pending_responses()
