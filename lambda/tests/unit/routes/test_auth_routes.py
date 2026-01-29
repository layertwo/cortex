"""Unit tests for authentication route handlers."""

import json

from src.entrypoint.api import lambda_handler


class TestLoginRoute:
    def test_login_route_handler_success(self, mock_service_provider):
        """Test login route handler returns expected response structure."""
        event = {
            "resource": "/v1/auth/login",
            "path": "/v1/auth/login",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"email": "test@example.com", "password": "testpassword123"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "message" in body, "Response should include message"
        assert "auth_type" in body, "Response should include auth_type"

        # Verify response values
        assert isinstance(body["message"], str), "message should be a string"
        assert isinstance(body["auth_type"], str), "auth_type should be a string"
        assert (
            body["auth_type"] == "cognito"
        ), f"auth_type should be 'cognito', got {body['auth_type']}"

    def test_login_route_handler_missing_email(self, mock_service_provider):
        """Test login route handler returns error when email is missing."""
        event = {
            "resource": "/v1/auth/login",
            "path": "/v1/auth/login",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"password": "testpassword123"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body

    def test_login_route_handler_missing_password(self, mock_service_provider):
        """Test login route handler returns error when password is missing."""
        event = {
            "resource": "/v1/auth/login",
            "path": "/v1/auth/login",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"email": "test@example.com"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body


class TestRefreshRoute:
    def test_refresh_route_handler_success(self, mock_service_provider):
        """Test refresh route handler returns expected response structure."""
        event = {
            "resource": "/v1/auth/refresh",
            "path": "/v1/auth/refresh",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"refresh_token": "test-refresh-token"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "message" in body, "Response should include message"
        assert "auth_type" in body, "Response should include auth_type"

        # Verify response values
        assert isinstance(body["message"], str), "message should be a string"
        assert isinstance(body["auth_type"], str), "auth_type should be a string"
        assert (
            body["auth_type"] == "cognito"
        ), f"auth_type should be 'cognito', got {body['auth_type']}"

    def test_refresh_route_handler_missing_token(self, mock_service_provider):
        """Test refresh route handler returns error when refresh_token is missing."""
        event = {
            "resource": "/v1/auth/refresh",
            "path": "/v1/auth/refresh",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body


class TestRecoverRoute:
    def test_recover_route_handler_success(self, mock_service_provider):
        """Test recover route handler returns expected response structure."""
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

        # Verify status code
        assert response["statusCode"] == 200

        # Verify response payload structure
        body = json.loads(response["body"])
        assert "message" in body, "Response should include message"
        assert "recovery_type" in body, "Response should include recovery_type"

        # Verify response values
        assert isinstance(body["message"], str), "message should be a string"
        assert isinstance(body["recovery_type"], str), "recovery_type should be a string"
        assert (
            body["recovery_type"] == "account_password"
        ), f"recovery_type should be 'account_password', got {body['recovery_type']}"

    def test_recover_route_handler_missing_email(self, mock_service_provider):
        """Test recover route handler returns error when email is missing."""
        event = {
            "resource": "/v1/auth/recover",
            "path": "/v1/auth/recover",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"recovery_code": "ABCD-EFGH-IJKL-MNOP"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body

    def test_recover_route_handler_missing_recovery_code(self, mock_service_provider):
        """Test recover route handler returns error when recovery_code is missing."""
        event = {
            "resource": "/v1/auth/recover",
            "path": "/v1/auth/recover",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"email": "test@example.com"}),
            "requestContext": {"requestId": "test-request-id"},
        }
        response = lambda_handler(event, {}, mock_service_provider)

        # Verify error response
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        # Powertools format: {"statusCode": 400, "message": "..."}
        assert body["statusCode"] == 400
        assert "message" in body
