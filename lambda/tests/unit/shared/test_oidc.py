"""Tests for OIDC bearer-token validation."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.shared import oidc
from src.shared.exceptions import UnauthorizedError

ISSUER = "https://idp.example.com"
CLIENT_ID = "cortex"


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _FakeJwkClient:
    def __init__(self, key):
        self._key = key

    def get_signing_key_from_jwt(self, token):
        return type("SigningKey", (), {"key": self._key.public_key()})()


@pytest.fixture(autouse=True)
def oidc_env(monkeypatch, signing_key):
    monkeypatch.setenv("OIDC_ISSUER", ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(oidc, "_jwks_uri", lambda issuer: f"{issuer}/jwks")
    monkeypatch.setattr(oidc, "_jwk_client", lambda uri: _FakeJwkClient(signing_key))


def _token(signing_key, **overrides):
    now = datetime.now(tz=timezone.utc)
    claims = {
        "sub": "user-1",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": "k1"})


class TestVerifyToken:
    def test_returns_the_subject_of_a_valid_token(self, signing_key):
        assert oidc.verify_token(_token(signing_key)) == "user-1"

    def test_rejects_another_audience(self, signing_key):
        with pytest.raises(UnauthorizedError):
            oidc.verify_token(_token(signing_key, aud="someone-else"))

    def test_rejects_another_issuer(self, signing_key):
        with pytest.raises(UnauthorizedError):
            oidc.verify_token(_token(signing_key, iss="https://evil.example.com"))

    def test_rejects_an_expired_token(self, signing_key):
        expired = datetime.now(tz=timezone.utc) - timedelta(minutes=1)
        with pytest.raises(UnauthorizedError):
            oidc.verify_token(_token(signing_key, exp=expired))

    def test_rejects_a_token_without_a_subject(self, signing_key):
        now = datetime.now(tz=timezone.utc)
        token = jwt.encode(
            {"iss": ISSUER, "aud": CLIENT_ID, "exp": now + timedelta(minutes=5)},
            signing_key,
            algorithm="RS256",
        )
        with pytest.raises(UnauthorizedError):
            oidc.verify_token(token)

    def test_rejects_when_oidc_is_not_configured(self, monkeypatch, signing_key):
        monkeypatch.delenv("OIDC_CLIENT_ID")
        with pytest.raises(UnauthorizedError, match="not configured"):
            oidc.verify_token(_token(signing_key))

    def test_rejects_when_the_provider_is_unreachable(self, monkeypatch, signing_key):
        def boom(_):
            raise OSError("no route to host")

        monkeypatch.setattr(oidc, "_jwks_uri", boom)
        with pytest.raises(UnauthorizedError):
            oidc.verify_token(_token(signing_key))
