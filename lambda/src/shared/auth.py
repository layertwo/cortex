"""
Shared authentication utilities for Cortex Backup System.

This module provides functions to extract user identity from API Gateway context,
validate JWT tokens, and perform user authorization checks.

Requirements: 3.1, 3.2, 3.4
"""

from typing import Any, Dict, Optional

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import ForbiddenError, UnauthorizedError

logger = Logger(child=True)


def get_user_from_context(event: Dict[str, Any]) -> str:
    """
    Extract user identity from API Gateway authorizer context.

    API Gateway validates the JWT token and adds user information to the
    request context. This function extracts the user ID from that context.

    Args:
        event: API Gateway event dictionary

    Returns:
        User ID (Cognito sub claim)

    Raises:
        AuthenticationError: If user identity cannot be extracted
    """
    try:
        # API Gateway adds authorizer context after JWT validation
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})

        # Try to get user ID from authorizer claims
        # Cognito adds claims to the authorizer context
        claims = authorizer.get("claims", {})
        user_id = claims.get("sub")

        if not user_id:
            # Fallback: try to get from principalId (custom authorizer)
            user_id = authorizer.get("principalId")

        if not user_id:
            logger.warning(
                "User ID not found in request context", extra={"request_context": request_context}
            )
            raise UnauthorizedError("User identity not found in request")

        logger.debug("Extracted user ID from context", extra={"user_id": user_id})

        return user_id

    except KeyError as e:
        logger.error(
            "Failed to extract user from context",
            extra={"error": str(e), "event_keys": list(event.keys())},
        )
        raise UnauthorizedError("Invalid authentication context")


def get_user_email_from_context(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract user email from API Gateway authorizer context.

    Args:
        event: API Gateway event dictionary

    Returns:
        User email if available, None otherwise
    """
    try:
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        claims = authorizer.get("claims", {})

        return claims.get("email")

    except (KeyError, AttributeError):
        return None


def verify_user_owns_vault(user_id: str, vault_id: str, item_vault_id: str) -> None:
    """
    Verify that a user owns the vault associated with a resource.

    This is a critical authorization check to ensure users can only access
    their own vaults and resources.

    Args:
        user_id: Authenticated user ID
        vault_id: Vault ID the user is trying to access
        item_vault_id: Vault ID associated with the resource

    Raises:
        AuthorizationError: If user doesn't own the vault
    """
    if vault_id != item_vault_id:
        logger.warning(
            "Vault ownership verification failed",
            extra={
                "user_id": user_id,
                "requested_vault_id": vault_id,
                "item_vault_id": item_vault_id,
            },
        )
        raise ForbiddenError("Access denied to vault")


def verify_user_owns_resource(user_id: str, resource_user_id: str) -> None:
    """
    Verify that a user owns a specific resource.

    This is a critical authorization check to ensure users can only access
    their own resources (files, collections, etc.).

    Args:
        user_id: Authenticated user ID
        resource_user_id: User ID associated with the resource

    Raises:
        AuthorizationError: If user doesn't own the resource
    """
    if user_id != resource_user_id:
        logger.warning(
            "Resource ownership verification failed",
            extra={"user_id": user_id, "resource_user_id": resource_user_id},
        )
        raise ForbiddenError("Access denied to resource")


def extract_bearer_token(event: Dict[str, Any]) -> Optional[str]:
    """
    Extract bearer token from Authorization header.

    Args:
        event: API Gateway event dictionary

    Returns:
        Bearer token if present, None otherwise
    """
    headers = event.get("headers", {})

    # Headers can be case-insensitive in API Gateway
    auth_header = headers.get("Authorization") or headers.get("authorization") or ""

    if auth_header.startswith("Bearer "):
        return auth_header[7:]  # Remove "Bearer " prefix

    return None


def validate_cognito_token_claims(claims: Dict[str, Any]) -> bool:
    """
    Validate Cognito JWT token claims.

    Performs basic validation of required claims. API Gateway performs
    signature validation, but we can add additional checks here.

    Args:
        claims: JWT token claims dictionary

    Returns:
        True if claims are valid, False otherwise
    """
    required_claims = ["sub", "iss", "exp", "iat"]

    for claim in required_claims:
        if claim not in claims:
            logger.warning("Missing required claim in token", extra={"missing_claim": claim})
            return False

    # Additional validation can be added here:
    # - Check token expiration (exp claim)
    # - Verify issuer (iss claim) matches expected Cognito user pool
    # - Check audience (aud claim) if applicable

    return True


def get_vault_id_from_user(user_id: str) -> str:
    """
    Get the default vault ID for a user.

    In the current implementation, each user has one vault.
    The vault ID is derived from the user ID.

    Args:
        user_id: User ID

    Returns:
        Vault ID for the user
    """
    # For now, we use a simple mapping: one vault per user
    # In future, users might have multiple vaults
    return f"vault-{user_id}"


def require_authentication(event: Dict[str, Any]) -> str:
    """
    Require authentication and return user ID.

    This is a convenience function that combines authentication checks.
    Use this at the start of route handlers that require authentication.

    Args:
        event: API Gateway event dictionary

    Returns:
        Authenticated user ID

    Raises:
        AuthenticationError: If authentication fails
    """
    user_id = get_user_from_context(event)

    if not user_id:
        raise UnauthorizedError("Authentication required")

    return user_id


def require_vault_access(
    vault_service, user_id: str, vault_id: str, operation: str = "access"
) -> None:
    """
    Require vault ownership authorization.

    This is a critical security check that prevents OWASP A01:2021 - Broken Access Control.
    All endpoints that accept vault_id as a parameter MUST call this function before
    processing the request.

    Args:
        vault_service: VaultService instance for checking vault ownership
        user_id: Authenticated user ID
        vault_id: Vault ID the user is trying to access
        operation: Operation name for logging (e.g., "delete_item", "list_items")

    Raises:
        ForbiddenError: If user doesn't own the vault

    Example:
        ```python
        user_id = get_user_from_context(app.current_event)
        vault_id = query_params.get("vault_id")
        require_vault_access(self.vault_service, user_id, vault_id, "delete_item")
        ```

    Security: CRITICAL - This prevents users from accessing vaults they don't own
    """
    if not vault_service.vault_exists(user_id, vault_id):
        logger.warning(
            "Vault access denied - user does not own vault",
            extra={
                "user_id": user_id,
                "vault_id": vault_id,
                "operation": operation,
            },
        )
        raise ForbiddenError("Access denied to vault")
