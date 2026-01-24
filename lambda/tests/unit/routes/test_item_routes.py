"""
Unit tests for item route handlers.

Tests verify that item routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestCreateItemRoute:
    """Test suite for CreateItemRoute through lambda handler."""

    def test_create_item_route_handler(self, mock_service_provider):
        """Test create item route handler returns expected response."""
        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Create item endpoint" in body["message"]


class TestInitiateUploadRoute:
    """Test suite for InitiateUploadRoute through lambda handler."""

    def test_initiate_upload_route_handler(self, mock_service_provider):
        """Test initiate upload route handler returns expected response."""
        event = {
            "resource": "/v1/items/upload/init",
            "path": "/v1/items/upload/init",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Initiate upload endpoint" in body["message"]


class TestCompleteUploadRoute:
    """Test suite for CompleteUploadRoute through lambda handler."""

    def test_complete_upload_route_handler(self, mock_service_provider):
        """Test complete upload route handler returns expected response."""
        event = {
            "resource": "/v1/items/upload/complete",
            "path": "/v1/items/upload/complete",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Complete upload endpoint" in body["message"]


class TestListItemsRoute:
    """Test suite for ListItemsRoute through lambda handler."""

    def test_list_items_route_handler(self, mock_service_provider):
        """Test list items route handler returns expected response."""
        event = {
            "resource": "/v1/items",
            "path": "/v1/items",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "List items endpoint" in body["message"]


class TestGetItemRoute:
    """Test suite for GetItemRoute through lambda handler."""

    def test_get_item_route_handler(self, mock_service_provider):
        """Test get item route handler returns expected response."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Get item endpoint" in body["message"]


class TestUpdateItemRoute:
    """Test suite for UpdateItemRoute through lambda handler."""

    def test_update_item_route_handler(self, mock_service_provider):
        """Test update item route handler returns expected response."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "PUT",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Update item endpoint" in body["message"]


class TestDeleteItemRoute:
    """Test suite for DeleteItemRoute through lambda handler."""

    def test_delete_item_route_handler(self, mock_service_provider):
        """Test delete item route handler returns expected response."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}",
            "path": f"/v1/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Delete item endpoint" in body["message"]


class TestDownloadItemRoute:
    """Test suite for DownloadItemRoute through lambda handler."""

    def test_download_item_route_handler(self, mock_service_provider):
        """Test download item route handler returns expected response."""
        item_id = "test-item-123"
        event = {
            "resource": "/v1/items/{item_id}/download",
            "path": f"/v1/items/{item_id}/download",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"item_id": item_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Download item endpoint" in body["message"]


class TestSearchItemRoute:
    """Test suite for SearchItemsRoute through lambda handler."""

    def test_search_items_route_handler(self, mock_service_provider):
        """Test search items route handler returns expected response."""
        event = {
            "resource": "/v1/items/search",
            "path": "/v1/items/search",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Search items endpoint" in body["message"]
