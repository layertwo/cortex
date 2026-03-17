"""Tests for domain exceptions."""

from src.shared.exceptions import (
    BadRequestError,
    InternalError,
    NotFoundError,
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
