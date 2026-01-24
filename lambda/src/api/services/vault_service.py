"""
Vault service layer for Cortex API.

This module implements business logic for vault management including
vault creation with salt generation and vault salt retrieval.

Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5
"""

import secrets
import time
import uuid
from typing import Dict, Optional

from aws_lambda_powertools import Logger
from boto3.dynamodb.types import Binary
from botocore.exceptions import ClientError

from src.shared.errors import ResourceNotFoundError, StorageError, ValidationError

logger = Logger(child=True)


class VaultService:
    """Service for vault management operations."""

    def __init__(self, vaults_table):
        """
        Initialize vault service.

        Args:
            vaults_table: DynamoDB vaults table resource
        """
        self.vaults_table = vaults_table

    def create_vault(self, user_id: str, vault_salt: Optional[bytes] = None) -> Dict:
        """
        Create a new vault with a unique vault salt.

        The vault salt is a 16-byte cryptographically secure random value
        that is stored on the server and used by the client for key derivation.
        The salt is non-secret information that enables multi-device access.

        Args:
            user_id: User identifier
            vault_salt: Optional 16-byte vault salt (if not provided, will be generated)

        Returns:
            Dictionary containing vault_id, vault_salt, and created_at

        Raises:
            ValidationError: If vault_salt is provided but invalid
            StorageError: If DynamoDB operation fails

        Requirements: 14.4, 22.1, 22.2, 22.3, 22.4, 22.5
        """
        # Generate vault ID
        vault_id = str(uuid.uuid4())

        # Generate or validate vault salt
        if vault_salt is None:
            # Generate 16-byte cryptographically secure random salt
            vault_salt = secrets.token_bytes(16)
            logger.info("Generated vault salt", extra={"vault_id": vault_id, "user_id": user_id})
        else:
            # Validate provided salt
            if not isinstance(vault_salt, bytes) or len(vault_salt) != 16:
                raise ValidationError("Vault salt must be exactly 16 bytes")

        # Create timestamp
        created_at = int(time.time())

        # Build DynamoDB item
        item = {
            "PK": f"USER#{user_id}",
            "SK": f"VAULT#{vault_id}",
            "vault_id": vault_id,
            "user_id": user_id,
            "vault_salt": vault_salt,
            "created_at": created_at,
        }

        try:
            # Store vault in DynamoDB
            # Use condition to ensure vault_id uniqueness (though UUID collision is extremely unlikely)
            self.vaults_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )

            logger.info(
                "Vault created successfully",
                extra={"vault_id": vault_id, "user_id": user_id, "salt_length": len(vault_salt)},
            )

            return {"vault_id": vault_id, "vault_salt": vault_salt, "created_at": created_at}

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")

            if error_code == "ConditionalCheckFailedException":
                # Extremely unlikely UUID collision - retry with new ID
                logger.warning(
                    "Vault ID collision detected, retrying",
                    extra={"vault_id": vault_id, "user_id": user_id},
                )
                # Recursive retry (UUID collision is astronomically unlikely)
                return self.create_vault(user_id, vault_salt)

            logger.error(
                "Failed to create vault",
                extra={"error": str(e), "vault_id": vault_id, "user_id": user_id},
            )
            raise StorageError("Failed to create vault")

    def get_vault_salt(self, user_id: str, vault_id: str) -> bytes:
        """
        Retrieve vault salt for key derivation.

        The vault salt is non-secret information that the client needs
        to derive the vault master key from the vault password using Argon2id.
        This enables multi-device access with the same vault password.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Returns:
            16-byte vault salt

        Raises:
            ResourceNotFoundError: If vault not found or user doesn't own vault
            StorageError: If DynamoDB operation fails

        Requirements: 14.4, 22.3, 22.5
        """
        try:
            # Query DynamoDB for vault
            response = self.vaults_table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
            )

            item = response.get("Item")

            if not item:
                logger.warning(
                    "Vault not found",
                    extra={"vault_id": vault_id, "user_id": user_id, "operation": "get_salt"},
                )
                raise ResourceNotFoundError(f"Vault {vault_id} not found")

            vault_salt = item.get("vault_salt")

            if not vault_salt:
                logger.error(
                    "Vault salt missing from vault item",
                    extra={"vault_id": vault_id, "user_id": user_id},
                )
                raise StorageError("Vault salt not found in vault record")

            # Convert Binary type to bytes if necessary
            if isinstance(vault_salt, Binary):
                vault_salt = bytes(vault_salt)

            # Validate salt format
            if not isinstance(vault_salt, bytes) or len(vault_salt) != 16:
                logger.error(
                    "Invalid vault salt format",
                    extra={
                        "vault_id": vault_id,
                        "user_id": user_id,
                        "salt_type": type(vault_salt).__name__,
                        "salt_length": len(vault_salt) if isinstance(vault_salt, bytes) else None,
                    },
                )
                raise StorageError("Invalid vault salt format")

            logger.info(
                "Vault salt retrieved successfully",
                extra={"vault_id": vault_id, "user_id": user_id, "salt_length": len(vault_salt)},
            )

            return vault_salt

        except ClientError as e:
            logger.error(
                "Failed to retrieve vault salt",
                extra={"error": str(e), "vault_id": vault_id, "user_id": user_id},
            )
            raise StorageError("Failed to retrieve vault salt")

    def vault_exists(self, user_id: str, vault_id: str) -> bool:
        """
        Check if a vault exists for a user.

        Args:
            user_id: User identifier
            vault_id: Vault identifier

        Returns:
            True if vault exists, False otherwise
        """
        try:
            response = self.vaults_table.get_item(
                Key={"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"}
            )

            return "Item" in response

        except ClientError as e:
            logger.error(
                "Failed to check vault existence",
                extra={"error": str(e), "vault_id": vault_id, "user_id": user_id},
            )
            return False

    def list_user_vaults(self, user_id: str) -> list:
        """
        List all vaults for a user.

        Args:
            user_id: User identifier

        Returns:
            List of vault dictionaries

        Raises:
            StorageError: If DynamoDB operation fails
        """
        try:
            response = self.vaults_table.query(
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={":pk": f"USER#{user_id}", ":sk_prefix": "VAULT#"},
            )

            vaults = []
            for item in response.get("Items", []):
                vaults.append(
                    {
                        "vault_id": item["vault_id"],
                        "created_at": item["created_at"],
                        # Note: vault_salt is intentionally excluded from list response
                        # Clients should fetch salt explicitly when needed
                    }
                )

            logger.info("Listed user vaults", extra={"user_id": user_id, "count": len(vaults)})

            return vaults

        except ClientError as e:
            logger.error("Failed to list user vaults", extra={"error": str(e), "user_id": user_id})
            raise StorageError("Failed to list vaults")
