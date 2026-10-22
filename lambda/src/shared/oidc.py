"""
OIDC bearer-token validation for direct deployments.

API Gateway has already validated the token when Cortex runs as a Lambda, so this
module is only used by the container/homelab deployment. It validates the ID token
the SPA gets from the OIDC provider (Pocket ID, or Cognito's hosted UI) against the
provider's JWKS. Claims are never logged: the subject is PII.
"""

import json
import os
import urllib.request
from functools import lru_cache

import jwt
from jwt import PyJWKClient

from src.shared.exceptions import UnauthorizedError
from src.shared.logger import get_logger

logger = get_logger("oidc")

_ALGORITHMS = ["RS256", "ES256"]


@lru_cache(maxsize=8)
def _jwk_client(jwks_uri: str) -> PyJWKClient:
    """JWKS client per provider; it caches keys and refetches on an unknown kid."""
    return PyJWKClient(jwks_uri, timeout=5)


@lru_cache(maxsize=8)
def _jwks_uri(issuer: str) -> str:
    """Resolve the provider's JWKS URL from its OIDC discovery document."""
    url = f"{issuer}/.well-known/openid-configuration"
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)["jwks_uri"]


def verify_token(token: str) -> str:
    """
    Validate an OIDC ID token and return its subject.

    Raises:
        UnauthorizedError: if the token is malformed, expired, for another
            audience/issuer, or the provider is unreachable.
    """
    issuer = os.environ.get("OIDC_ISSUER", "").rstrip("/")
    client_id = os.environ.get("OIDC_CLIENT_ID", "")
    if not issuer or not client_id:
        logger.error("OIDC issuer/client id not configured")
        raise UnauthorizedError("Authentication is not configured")

    try:
        signing_key = _jwk_client(_jwks_uri(issuer)).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            audience=client_id,
            issuer=issuer,
            leeway=60,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.warning("OIDC token rejected", error_type=type(exc).__name__)
        raise UnauthorizedError("Invalid or expired token") from exc
    except Exception as exc:
        # Discovery/JWKS fetch failures are auth failures: without keys we cannot trust it.
        logger.warning("OIDC key lookup failed", error_type=type(exc).__name__)
        raise UnauthorizedError("Unable to verify token") from exc

    return claims["sub"]
