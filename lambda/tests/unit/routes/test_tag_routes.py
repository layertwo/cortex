"""
Unit tests for tag route handlers.

Tests verify that tag routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestSearchTagsRoute:
    """Test suite for SearchTagsRoute through lambda handler."""

    def test_search_tags_route_handler(self, mock_service_provider):
        """Test search tags route handler returns expected response."""
        event = {
            "resource": "/v1/tags/search",
            "path": "/v1/tags/search",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Search tags endpoint" in body["message"]
