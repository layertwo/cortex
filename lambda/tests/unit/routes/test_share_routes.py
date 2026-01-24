"""
Unit tests for share route handlers.

Tests verify that share routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestCreateShareRoute:
    """Test suite for CreateShareRoute through lambda handler."""

    def test_create_share_route_handler(self, mock_service_provider):
        """Test create share route handler returns expected response."""
        event = {
            "resource": "/v1/shares",
            "path": "/v1/shares",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Create share endpoint" in body["message"]


class TestGetShareRoute:
    """Test suite for GetShareRoute through lambda handler."""

    def test_get_share_route_handler(self, mock_service_provider):
        """Test get share route handler returns expected response."""
        share_id = "test-share-123"
        event = {
            "resource": "/v1/shares/{share_id}",
            "path": f"/v1/shares/{share_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"share_id": share_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Get share endpoint" in body["message"]


class TestRevokeShareRoute:
    """Test suite for RevokeShareRoute through lambda handler."""

    def test_revoke_share_route_handler(self, mock_service_provider):
        """Test revoke share route handler returns expected response."""
        share_id = "test-share-123"
        event = {
            "resource": "/v1/shares/{share_id}",
            "path": f"/v1/shares/{share_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"share_id": share_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Revoke share endpoint" in body["message"]
