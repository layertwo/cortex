"""
Authentication utilities for Cortex API.

API Gateway (Lambda/Mangum) has already validated the Cognito token, so the
subject comes from the authorizer context. Direct/container deployments (the
homelab) validate the OIDC bearer token the SPA sends against the provider's JWKS.
"""

from typing import Any, Dict

from fastapi import Request

from src.shared.exceptions import UnauthorizedError
from src.shared.logger import get_logger
from src.shared.oidc import verify_token

logger = get_logger("auth")


def extract_user_id(event: Dict[str, Any]) -> str:
    """
    Extract user ID from an API Gateway event dictionary.

    Args:
        event: API Gateway event (available via Mangum's ASGI scope)

    Returns:
        User ID string

    Raises:
        UnauthorizedError: If user identity cannot be extracted
    """
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})

    # Try Cognito claims first
    claims = authorizer.get("claims", {})
    user_id = claims.get("sub")

    if not user_id:
        # Fallback to custom authorizer principalId
        user_id = authorizer.get("principalId")

    if not user_id:
        has_authorizer = bool(authorizer)
        logger.warning("user_id_not_found", has_authorizer=has_authorizer)
        raise UnauthorizedError("User identity not found in request")

    return user_id


def _bearer_token(request: Request) -> str:
    """Read the OIDC token from the Authorization header."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Authentication required")
    return token.strip()


def get_current_user(request: Request) -> str:
    """
    FastAPI dependency that resolves the current user ID.

    In Lambda (Mangum): from the API Gateway authorizer context.
    Elsewhere: by validating the OIDC bearer token against the provider's JWKS.
    """
    # Mangum stores the original API Gateway event in scope
    aws_event = request.scope.get("aws.event")
    if aws_event:
        return extract_user_id(aws_event)

    token = _bearer_token(request)
    config = request.app.state.config
    return verify_token(
        token,
        issuer=config.oidc_issuer,
        client_id=config.oidc_client_id,
    )
