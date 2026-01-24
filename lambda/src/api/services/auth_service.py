"""
Authentication service layer for Cortex API.

This module implements authentication business logic including login validation,
token refresh, and account recovery with recovery codes.

Requirements: 3.1, 3.2, 19.1, 19.2, 19.3, 19.5
"""

import hashlib
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from aws_lambda_powertools import Logger

from src.shared.errors import (
    RecoveryCodeInvalidError,
    ValidationError,
)

logger = Logger(child=True)

# Recovery code configuration
RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_LENGTH = 16  # Total characters (excluding dashes)
RECOVERY_CODE_FORMAT = "XXXX-XXXX-XXXX-XXXX"


class AuthService:
    """
    Authentication service for handling login, token refresh, and account recovery.

    This service handles account password authentication via Cognito and
    account recovery using recovery codes.
    """

    def __init__(self, recovery_table, cognito_client=None, user_pool_id: Optional[str] = None):
        """
        Initialize the authentication service.

        Args:
            recovery_table: DynamoDB table resource for recovery codes
            cognito_client: Optional Cognito client for authentication
            user_pool_id: Optional Cognito user pool ID
        """
        self.recovery_table = recovery_table
        self.cognito_client = cognito_client
        self.user_pool_id = user_pool_id

    def validate_login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Validate user login credentials.

        Note: In production, this would authenticate against Cognito.
        The actual authentication is handled by API Gateway + Cognito authorizer.
        This method is for custom authentication flows.

        Args:
            email: User email address
            password: Account password (not vault password)

        Returns:
            Authentication result with tokens

        Raises:
            AuthenticationError: If credentials are invalid
        """
        if not email or not password:
            raise ValidationError("Email and password are required")

        # In production, this would call Cognito's InitiateAuth
        # For now, we return a placeholder indicating the flow
        logger.info("Login validation requested", extra={"email_domain": email.split("@")[-1]})

        # The actual authentication is handled by Cognito via API Gateway
        # This endpoint is for initiating custom auth flows
        return {
            "message": "Authentication handled by Cognito authorizer",
            "auth_type": "cognito",
        }

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh authentication tokens.

        Note: In production, this would call Cognito's token refresh endpoint.

        Args:
            refresh_token: Refresh token from previous authentication

        Returns:
            New authentication tokens

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        if not refresh_token:
            raise ValidationError("Refresh token is required")

        logger.info("Token refresh requested")

        # The actual token refresh is handled by Cognito
        return {
            "message": "Token refresh handled by Cognito",
            "auth_type": "cognito",
        }

    def initiate_recovery(self, email: str, recovery_code: str) -> Dict[str, Any]:
        """
        Initiate account recovery using a recovery code.

        This validates the recovery code and allows the user to reset their
        account password. Note: This does NOT affect vault encryption keys.

        Args:
            email: User email address
            recovery_code: One of the user's recovery codes

        Returns:
            Recovery session information

        Raises:
            RecoveryCodeInvalidError: If recovery code is invalid or already used
            AuthenticationError: If user not found
        """
        if not email or not recovery_code:
            raise ValidationError("Email and recovery code are required")

        logger.info(
            "Account recovery initiated",
            extra={"email_domain": email.split("@")[-1]},
        )

        # Normalize the recovery code (remove dashes, uppercase)
        normalized_code = self._normalize_recovery_code(recovery_code)

        # Hash the code for lookup
        self._hash_recovery_code(normalized_code)

        # This would look up the user by email first, then validate the code
        # For now, return placeholder indicating the flow
        return {
            "message": "Recovery code validation - implementation pending user lookup",
            "recovery_type": "account_password",
        }

    def generate_recovery_codes(self, user_id: str) -> Tuple[List[str], int]:
        """
        Generate account recovery codes for a user.

        Generates 10 recovery codes in format XXXX-XXXX-XXXX-XXXX.
        Codes are hashed with SHA-256 before storage.

        Args:
            user_id: User identifier

        Returns:
            Tuple of (list of plaintext codes to display once, generation timestamp)

        Requirements: 19.1
        """
        if not user_id:
            raise ValidationError("User ID is required")

        logger.info("Generating recovery codes", extra={"user_id": user_id})

        # Generate recovery codes
        codes = []
        for _ in range(RECOVERY_CODE_COUNT):
            code = self._generate_recovery_code()
            codes.append(code)

        # Store hashed codes in DynamoDB
        timestamp = int(time.time())
        self._store_recovery_codes(user_id, codes, timestamp)

        return codes, timestamp

    def validate_recovery_code(self, user_id: str, recovery_code: str) -> bool:
        """
        Validate a recovery code for account recovery.

        If valid, the code is marked as used and cannot be reused.

        Args:
            user_id: User identifier
            recovery_code: Recovery code to validate

        Returns:
            True if code is valid

        Raises:
            RecoveryCodeInvalidError: If code is invalid or already used

        Requirements: 19.2, 19.3
        """
        if not user_id or not recovery_code:
            raise ValidationError("User ID and recovery code are required")

        # Normalize and hash the code
        normalized_code = self._normalize_recovery_code(recovery_code)
        code_hash = self._hash_recovery_code(normalized_code)

        # Look up the code in DynamoDB
        key = {"PK": f"USER#{user_id}", "SK": f"RECOVERY#{code_hash}"}

        try:
            response = self.recovery_table.get_item(Key=key)
            item = response.get("Item")

            if not item:
                logger.warning(
                    "Recovery code not found",
                    extra={"user_id": user_id},
                )
                raise RecoveryCodeInvalidError()

            # Check if code is still valid (not used)
            if not item.get("is_valid", False):
                logger.warning(
                    "Recovery code already used",
                    extra={"user_id": user_id},
                )
                raise RecoveryCodeInvalidError("Recovery code has already been used")

            # Mark code as used
            self._invalidate_recovery_code(user_id, code_hash)

            logger.info(
                "Recovery code validated successfully",
                extra={"user_id": user_id},
            )

            return True

        except RecoveryCodeInvalidError:
            raise
        except Exception as e:
            logger.error(
                "Error validating recovery code",
                extra={"user_id": user_id, "error": str(e)},
            )
            raise RecoveryCodeInvalidError()

    def _generate_recovery_code(self) -> str:
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

    def _normalize_recovery_code(self, code: str) -> str:
        """
        Normalize a recovery code for comparison.

        Removes dashes and converts to uppercase.

        Args:
            code: Recovery code (may include dashes)

        Returns:
            Normalized code (uppercase, no dashes)
        """
        return code.replace("-", "").upper()

    def _hash_recovery_code(self, code: str) -> str:
        """
        Hash a recovery code using SHA-256.

        Args:
            code: Normalized recovery code

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    def _store_recovery_codes(self, user_id: str, codes: List[str], timestamp: int) -> None:
        """
        Store hashed recovery codes in DynamoDB.

        Args:
            user_id: User identifier
            codes: List of plaintext recovery codes
            timestamp: Generation timestamp
        """
        for code in codes:
            normalized = self._normalize_recovery_code(code)
            code_hash = self._hash_recovery_code(normalized)

            item = {
                "PK": f"USER#{user_id}",
                "SK": f"RECOVERY#{code_hash}",
                "user_id": user_id,
                "code_hash": code_hash,
                "created_at": timestamp,
                "used_at": None,
                "is_valid": True,
            }

            self.recovery_table.put_item(Item=item)

        logger.info(
            "Stored recovery codes",
            extra={"user_id": user_id, "code_count": len(codes)},
        )

    def _invalidate_recovery_code(self, user_id: str, code_hash: str) -> None:
        """
        Mark a recovery code as used.

        Args:
            user_id: User identifier
            code_hash: SHA-256 hash of the recovery code

        Requirements: 19.3, 19.5
        """
        key = {"PK": f"USER#{user_id}", "SK": f"RECOVERY#{code_hash}"}
        timestamp = int(time.time())

        self.recovery_table.update_item(
            Key=key,
            UpdateExpression="SET is_valid = :valid, used_at = :used_at",
            ExpressionAttributeValues={":valid": False, ":used_at": timestamp},
        )

        logger.info(
            "Recovery code invalidated",
            extra={"user_id": user_id},
        )
