"""Tests for domain exceptions."""

from src.shared.exceptions import (
    BadRequestError,
    InternalError,
    NotFoundError,
    RateLimitExceededError,
    ShareExpiredError,
    ShareRevokedError,
    UnauthorizedError,
)


class TestDomainExceptions:
    def test_bad_request_has_message(self):
        err = BadRequestError("invalid input")
        assert str(err) == "invalid input"
        assert err.status_code == 400

    def test_not_found_has_message(self):
        err = NotFoundError("item not found")
        assert str(err) == "item not found"
        assert err.status_code == 404

    def test_unauthorized_has_message(self):
        err = UnauthorizedError("not authenticated")
        assert str(err) == "not authenticated"
        assert err.status_code == 401

    def test_internal_error_has_message(self):
        err = InternalError("something broke")
        assert str(err) == "something broke"
        assert err.status_code == 500

    def test_exceptions_inherit_from_base(self):
        from src.shared.exceptions import CortexError

        assert issubclass(BadRequestError, CortexError)
        assert issubclass(NotFoundError, CortexError)
        assert issubclass(UnauthorizedError, CortexError)
        assert issubclass(InternalError, CortexError)


def test_domain_errors_have_stable_codes():
    assert BadRequestError().code == "BAD_REQUEST"
    assert UnauthorizedError().code == "AUTHENTICATION_REQUIRED"
    assert NotFoundError().code == "NOT_FOUND"
    assert InternalError().code == "INTERNAL_ERROR"


def test_share_revoked_is_410_with_code():
    err = ShareRevokedError()
    assert err.status_code == 410
    assert err.code == "SHARE_REVOKED"
    assert err.message == "Share has been revoked"


def test_share_expired_is_410_with_code():
    err = ShareExpiredError()
    assert err.status_code == 410
    assert err.code == "SHARE_EXPIRED"
    assert err.message == "Share has expired"


def test_rate_limit_is_429_with_retry_after():
    err = RateLimitExceededError(retry_after=42)
    assert err.status_code == 429
    assert err.code == "RATE_LIMIT_EXCEEDED"
    assert err.retry_after == 42
    assert RateLimitExceededError().retry_after == 3600
