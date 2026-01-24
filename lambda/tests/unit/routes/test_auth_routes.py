"""
Unit tests for authentication route handlers.

Tests verify that auth routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestLoginRoute:
    """Test suite for LoginRoute through lambda handler."""

    def test_login_route_handler(self, mock_service_provider):
        """Test login route handler returns expected response."""
        event = {
            "resource": "/v1/auth/login",
            "path": "/v1/auth/login",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Login endpoint" in body["message"]


class TestRefreshRoute:
    """Test suite for RefreshRoute through lambda handler."""

    def test_refresh_route_handler(self, mock_service_provider):
        """Test refresh route handler returns expected response."""
        event = {
            "resource": "/v1/auth/refresh",
            "path": "/v1/auth/refresh",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Refresh endpoint" in body["message"]


class TestRecoverRoute:
    """Test suite for RecoverRoute through lambda handler."""

    def test_recover_route_handler(self, mock_service_provider):
        """Test recover route handler returns expected response."""
        event = {
            "resource": "/v1/auth/recover",
            "path": "/v1/auth/recover",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Recover endpoint" in body["message"]
