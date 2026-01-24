"""
Unit tests for recovery route handlers.

Tests verify that recovery routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestGenerateRecoveryCodesRoute:
    """Test suite for GenerateRecoveryCodesRoute through lambda handler."""

    def test_generate_recovery_codes_route_handler(self, mock_service_provider):
        """Test generate recovery codes route handler returns expected response."""
        event = {
            "resource": "/v1/recovery/codes",
            "path": "/v1/recovery/codes",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Generate recovery codes endpoint" in body["message"]


class TestValidateRecoveryCodeRoute:
    """Test suite for ValidateRecoveryCodeRoute through lambda handler."""

    def test_validate_recovery_code_route_handler(self, mock_service_provider):
        """Test validate recovery code route handler returns expected response."""
        event = {
            "resource": "/v1/recovery/validate",
            "path": "/v1/recovery/validate",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Validate recovery code endpoint" in body["message"]
