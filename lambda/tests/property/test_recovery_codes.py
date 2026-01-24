"""
Property-Based Tests for Account Recovery Code Validation

These tests verify that account recovery codes work correctly using
Hypothesis for property-based testing.

Property 25: Account recovery code validation

For any valid unused account recovery code, using it for account recovery
must grant access to the account and invalidate that specific code, while
leaving other codes valid.

Validates: Requirements 19.2, 19.3
"""

import hashlib
import secrets
import time
from typing import Dict, List

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Recovery code configuration (matching auth_service.py)
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_LENGTH = 16  # Total characters (excluding dashes)
RECOVERY_CODE_FORMAT = "XXXX-XXXX-XXXX-XXXX"


def generate_recovery_code() -> str:
    """
    Generate a single recovery code.

    Format: XXXX-XXXX-XXXX-XXXX (16 alphanumeric characters)

    Returns:
        Recovery code string
    """
    # Generate 16 random alphanumeric characters
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Exclude confusing chars (0,O,1,I)
    code_chars = "".join(secrets.choice(alphabet) for _ in range(RECOVERY_CODE_LENGTH))

    # Format as XXXX-XXXX-XXXX-XXXX
    return f"{code_chars[0:4]}-{code_chars[4:8]}-{code_chars[8:12]}-{code_chars[12:16]}"


def normalize_recovery_code(code: str) -> str:
    """
    Normalize a recovery code for comparison.

    Removes dashes and converts to uppercase.

    Args:
        code: Recovery code (may include dashes)

    Returns:
        Normalized code (uppercase, no dashes)
    """
    return code.replace("-", "").upper()


def hash_recovery_code(code: str) -> str:
    """
    Hash a recovery code using SHA-256.

    Args:
        code: Normalized recovery code

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


class RecoveryCodeStore:
    """
    Simulates the DynamoDB Account Recovery table.

    Stores recovery codes with their validation status.
    """

    def __init__(self):
        """Initialize the recovery code store."""
        self.codes: Dict[str, Dict[str, any]] = {}  # code_hash -> code_data

    def store_codes(self, user_id: str, codes: List[str], timestamp: int) -> None:
        """
        Store recovery codes for a user.

        Args:
            user_id: User identifier
            codes: List of plaintext recovery codes
            timestamp: Generation timestamp
        """
        for code in codes:
            normalized = normalize_recovery_code(code)
            code_hash = hash_recovery_code(normalized)

            key = f"{user_id}#{code_hash}"
            self.codes[key] = {
                "user_id": user_id,
                "code_hash": code_hash,
                "created_at": timestamp,
                "used_at": None,
                "is_valid": True,
            }

    def validate_code(self, user_id: str, code: str) -> bool:
        """
        Validate a recovery code.

        If valid, marks the code as used.

        Args:
            user_id: User identifier
            code: Recovery code to validate

        Returns:
            True if code is valid and unused, False otherwise
        """
        normalized = normalize_recovery_code(code)
        code_hash = hash_recovery_code(normalized)
        key = f"{user_id}#{code_hash}"

        if key not in self.codes:
            return False

        code_data = self.codes[key]

        if not code_data["is_valid"]:
            return False

        # Mark as used
        code_data["is_valid"] = False
        code_data["used_at"] = int(time.time())

        return True

    def is_code_valid(self, user_id: str, code: str) -> bool:
        """
        Check if a code is valid without marking it as used.

        Args:
            user_id: User identifier
            code: Recovery code to check

        Returns:
            True if code exists and is valid
        """
        normalized = normalize_recovery_code(code)
        code_hash = hash_recovery_code(normalized)
        key = f"{user_id}#{code_hash}"

        if key not in self.codes:
            return False

        return self.codes[key]["is_valid"]

    def count_valid_codes(self, user_id: str) -> int:
        """
        Count valid (unused) codes for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of valid codes
        """
        count = 0
        for key, data in self.codes.items():
            if data["user_id"] == user_id and data["is_valid"]:
                count += 1
        return count

    def get_all_codes(self, user_id: str) -> List[Dict[str, any]]:
        """
        Get all codes for a user.

        Args:
            user_id: User identifier

        Returns:
            List of code data dictionaries
        """
        return [data for key, data in self.codes.items() if data["user_id"] == user_id]


class TestRecoveryCodeValidation:
    """
    Property 25: Account recovery code validation

    For any valid unused account recovery code, using it for account recovery
    must grant access to the account and invalidate that specific code, while
    leaving other codes valid.

    Validates: Requirements 19.2, 19.3
    """

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_valid_unused_code_grants_access(self, user_id: str):
        """
        Property: A valid unused recovery code must grant access to the account.

        For any user with recovery codes, using a valid unused code must
        return True (grant access).
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Pick a random code to validate
        code_to_use = codes[0]

        # Validate the code - should grant access
        is_valid = store.validate_code(user_id, code_to_use)
        assert is_valid, "Valid unused code must grant access"

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_used_code_is_invalidated(self, user_id: str):
        """
        Property: Using a recovery code must invalidate that specific code.

        For any recovery code that has been used once, attempting to use it
        again must fail (return False).
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Use a code
        code_to_use = codes[0]
        first_validation = store.validate_code(user_id, code_to_use)
        assert first_validation, "First use should succeed"

        # Try to use the same code again
        second_validation = store.validate_code(user_id, code_to_use)
        assert not second_validation, "Used code must be invalidated"

    @given(st.text(min_size=1, max_size=50), st.integers(min_value=0, max_value=9))
    @settings(max_examples=100)
    def test_other_codes_remain_valid(self, user_id: str, code_index: int):
        """
        Property: Using one recovery code must not affect other codes.

        For any recovery code that is used, all other codes for the same
        user must remain valid.
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Use one code
        code_to_use = codes[code_index]
        store.validate_code(user_id, code_to_use)

        # Check that other codes are still valid
        for i, code in enumerate(codes):
            if i != code_index:
                is_valid = store.is_code_valid(user_id, code)
                assert is_valid, f"Code {i} should remain valid after using code {code_index}"

        # Count valid codes - should be 9 (10 - 1 used)
        valid_count = store.count_valid_codes(user_id)
        assert valid_count == RECOVERY_CODE_COUNT - 1

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_all_codes_can_be_used_once(self, user_id: str):
        """
        Property: Each recovery code can be used exactly once.

        For any set of recovery codes, each code can be successfully used
        once, and after all codes are used, no codes remain valid.
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Use all codes one by one
        for i, code in enumerate(codes):
            is_valid = store.validate_code(user_id, code)
            assert is_valid, f"Code {i} should be valid on first use"

            # Verify count decreases
            remaining = store.count_valid_codes(user_id)
            assert remaining == RECOVERY_CODE_COUNT - (i + 1)

        # After using all codes, none should be valid
        final_count = store.count_valid_codes(user_id)
        assert final_count == 0, "No codes should remain valid after all are used"

    @given(
        st.text(min_size=1, max_size=50),
        st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=100)
    def test_codes_are_user_specific(self, user1_id: str, user2_id: str):
        """
        Property: Recovery codes are user-specific.

        For any two different users, a recovery code from user1 must not
        grant access to user2's account.
        """
        # Skip if user IDs are the same
        if user1_id == user2_id:
            return

        store = RecoveryCodeStore()

        # Generate codes for user1
        user1_codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user1_id, user1_codes, timestamp)

        # Generate codes for user2
        user2_codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        store.store_codes(user2_id, user2_codes, timestamp)

        # Try to use user1's code for user2
        user1_code = user1_codes[0]
        is_valid_for_user2 = store.validate_code(user2_id, user1_code)
        assert not is_valid_for_user2, "User1's code must not work for user2"

        # Verify user1's code still works for user1
        is_valid_for_user1 = store.validate_code(user1_id, user1_code)
        assert is_valid_for_user1, "User1's code must work for user1"

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_invalid_code_does_not_grant_access(self, user_id: str):
        """
        Property: An invalid recovery code must not grant access.

        For any user with recovery codes, using a code that was never
        generated must fail.
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Try to use a code that was never generated
        invalid_code = "ZZZZ-ZZZZ-ZZZZ-ZZZZ"
        is_valid = store.validate_code(user_id, invalid_code)
        assert not is_valid, "Invalid code must not grant access"

        # Verify all original codes are still valid
        valid_count = store.count_valid_codes(user_id)
        assert valid_count == RECOVERY_CODE_COUNT

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_code_normalization_is_case_insensitive(self, user_id: str):
        """
        Property: Recovery code validation is case-insensitive.

        For any recovery code, it should work regardless of case
        (uppercase, lowercase, or mixed).
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Pick a code and test different cases
        original_code = codes[0]
        lowercase_code = original_code.lower()
        mixed_case_code = "".join(
            c.lower() if i % 2 == 0 else c.upper() for i, c in enumerate(original_code)
        )

        # All variations should be recognized as the same code
        # Test with lowercase
        is_valid_lower = store.validate_code(user_id, lowercase_code)
        assert is_valid_lower, "Lowercase code should be valid"

        # After using lowercase, the code should be invalidated
        # So trying with mixed case should fail
        is_valid_mixed = store.validate_code(user_id, mixed_case_code)
        assert not is_valid_mixed, "Code should be invalidated after first use"

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_code_normalization_ignores_dashes(self, user_id: str):
        """
        Property: Recovery code validation ignores dash placement.

        For any recovery code, it should work with or without dashes,
        and with dashes in different positions.
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Pick a code and test without dashes
        original_code = codes[0]
        code_without_dashes = original_code.replace("-", "")

        # Code without dashes should work
        is_valid = store.validate_code(user_id, code_without_dashes)
        assert is_valid, "Code without dashes should be valid"

    @given(
        st.text(min_size=1, max_size=50),
        st.lists(st.integers(min_value=0, max_value=9), min_size=1, max_size=10, unique=True),
    )
    @settings(max_examples=50)
    def test_partial_code_usage_maintains_remaining_codes(
        self, user_id: str, indices_to_use: List[int]
    ):
        """
        Property: Using some codes maintains the validity of remaining codes.

        For any subset of recovery codes that are used, the remaining codes
        must still be valid and usable.
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Use some codes
        used_indices = set(indices_to_use)
        for idx in used_indices:
            store.validate_code(user_id, codes[idx])

        # Check remaining codes are valid
        remaining_count = store.count_valid_codes(user_id)
        expected_remaining = RECOVERY_CODE_COUNT - len(used_indices)
        assert remaining_count == expected_remaining

        # Verify unused codes can still be used
        for i, code in enumerate(codes):
            if i not in used_indices:
                is_valid = store.is_code_valid(user_id, code)
                assert is_valid, f"Unused code {i} should still be valid"

    def test_recovery_code_format_is_correct(self):
        """
        Property: Generated recovery codes must follow the correct format.

        All recovery codes must be in format XXXX-XXXX-XXXX-XXXX with
        16 alphanumeric characters and 3 dashes.
        """
        for _ in range(100):
            code = generate_recovery_code()

            # Check length (16 chars + 3 dashes = 19)
            assert len(code) == 19, f"Code length should be 19, got {len(code)}"

            # Check dash positions
            assert code[4] == "-", "First dash should be at position 4"
            assert code[9] == "-", "Second dash should be at position 9"
            assert code[14] == "-", "Third dash should be at position 14"

            # Check characters are alphanumeric (excluding dashes)
            code_chars = code.replace("-", "")
            assert len(code_chars) == 16, "Should have 16 alphanumeric characters"
            assert code_chars.isalnum(), "All characters should be alphanumeric"
            assert code_chars.isupper(), "All characters should be uppercase"

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_code_hashing_is_deterministic(self, user_id: str):
        """
        Property: Hashing the same recovery code produces the same hash.

        For any recovery code, hashing it multiple times must produce
        the same hash value (deterministic hashing).
        """
        code = generate_recovery_code()
        normalized = normalize_recovery_code(code)

        # Hash the same code multiple times
        hash1 = hash_recovery_code(normalized)
        hash2 = hash_recovery_code(normalized)
        hash3 = hash_recovery_code(normalized)

        # All hashes should be identical
        assert hash1 == hash2 == hash3, "Hashing should be deterministic"

        # Hash should be SHA-256 (64 hex characters)
        assert len(hash1) == 64, "SHA-256 hash should be 64 hex characters"

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_ten_codes_are_generated(self, user_id: str):
        """
        Property: Exactly 10 recovery codes are generated per user.

        For any user, the system must generate exactly 10 recovery codes
        as specified in the requirements.
        """
        store = RecoveryCodeStore()

        # Generate recovery codes
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Verify count
        valid_count = store.count_valid_codes(user_id)
        assert valid_count == 10, "Exactly 10 recovery codes must be generated"

        # Verify all codes are unique
        unique_codes = set(codes)
        assert len(unique_codes) == 10, "All 10 codes must be unique"


class TestRecoveryCodeIntegration:
    """
    Integration tests for recovery code generation and validation flow.
    """

    def test_complete_recovery_flow(self):
        """
        Test: Complete account recovery flow with code generation and validation.
        """
        store = RecoveryCodeStore()
        user_id = "test-user-123"

        # Step 1: Generate recovery codes at signup
        codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        timestamp = int(time.time())
        store.store_codes(user_id, codes, timestamp)

        # Step 2: User loses access and uses a recovery code
        recovery_code = codes[3]  # User uses the 4th code
        is_valid = store.validate_code(user_id, recovery_code)
        assert is_valid, "Recovery code should grant access"

        # Step 3: Verify code is now invalid
        is_still_valid = store.is_code_valid(user_id, recovery_code)
        assert not is_still_valid, "Used code should be invalid"

        # Step 4: Verify other codes still work
        another_code = codes[7]  # User uses the 8th code later
        is_valid_2 = store.validate_code(user_id, another_code)
        assert is_valid_2, "Other codes should still work"

        # Step 5: Verify count is correct
        remaining = store.count_valid_codes(user_id)
        assert remaining == 8, "Should have 8 codes remaining (10 - 2 used)"

    def test_multiple_users_independent_codes(self):
        """
        Test: Multiple users have independent recovery codes.
        """
        store = RecoveryCodeStore()

        # Create codes for multiple users
        users = ["user-1", "user-2", "user-3"]
        user_codes = {}

        for user_id in users:
            codes = [generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
            timestamp = int(time.time())
            store.store_codes(user_id, codes, timestamp)
            user_codes[user_id] = codes

        # Each user should have 10 valid codes
        for user_id in users:
            count = store.count_valid_codes(user_id)
            assert count == 10

        # Use a code for user-1
        store.validate_code("user-1", user_codes["user-1"][0])

        # Verify only user-1's count decreased
        assert store.count_valid_codes("user-1") == 9
        assert store.count_valid_codes("user-2") == 10
        assert store.count_valid_codes("user-3") == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
