"""Unit tests for authentication route handlers."""

import json

from src.entrypoint.api import lambda_handler


class TestLoginRoute:
    def test_login_route_handler_success(self, mock_service_provider):
        event = {
            "resource": "/v1/auth/login",
            "path": "/v1/auth/login",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"email": "test@example.com", "password": "testpassword123"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)
        assert response["statusCode"] == 200


class TestRefreshRoute:
    def test_refresh_route_handler_success(self, mock_service_provider):
        event = {
            "resource": "/v1/auth/refresh",
            "path": "/v1/auth/refresh",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"refresh_token": "test-refresh-token"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)
        assert response["statusCode"] == 200


class TestRecoverRoute:
    def test_recover_route_handler_success(self, mock_service_provider):
        event = {
            "resource": "/v1/auth/recover",
            "path": "/v1/auth/recover",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(
                {"email": "test@example.com", "recovery_code": "ABCD-EFGH-IJKL-MNOP"}
            ),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)
        assert response["statusCode"] == 200
