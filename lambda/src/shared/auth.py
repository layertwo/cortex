"""
Authentication utilities for Cortex API.

Provides user identity extraction that works with both
API Gateway (Lambda/Mangum) and standalone container deployments.

Container mode requires an authenticating reverse proxy (nginx, Envoy, ALB)
that validates user credentials and sets the X-User-Id header. The proxy
MUST strip any client-provided X-User-Id headers to prevent spoofing.
"""

import os
from typing import Any, Dict

from fastapi import Request

from src.shared.exceptions import UnauthorizedError
from src.shared.logger import get_logger

logger = get_logger("auth")

# When set, container mode trusts X-User-Id from the auth proxy.
# Must only be enabled behind a properly configured reverse proxy.
_TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS", "false").lower() == "true"


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
        logger.warning("user_id_not_found", request_context=str(request_context))
        raise UnauthorizedError("User identity not found in request")

    return user_id


def get_current_user(request: Request) -> str:
    """
    FastAPI dependency that extracts the current user ID.

    In Lambda (Mangum): extracts from API Gateway authorizer context.
    In containers: extracts from X-User-Id header set by an authenticating
    reverse proxy. Requires TRUST_PROXY_HEADERS=true to enable.
    """
    # Mangum stores the original API Gateway event in scope
    aws_event = request.scope.get("aws.event")
    if aws_event:
        return extract_user_id(aws_event)

    # Container mode: trust proxy header only when explicitly enabled
    if _TRUST_PROXY_HEADERS:
        user_id = request.headers.get("x-user-id")
        if user_id:
            return user_id

    raise UnauthorizedError("User identity not found in request")
