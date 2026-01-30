"""
Shared authentication utilities for Cortex Backup System.

This module provides functions to extract user identity from API Gateway context,
validate JWT tokens, and perform user authorization checks.

Requirements: 3.1, 3.2, 3.4
"""

from typing import Any, Dict

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

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
