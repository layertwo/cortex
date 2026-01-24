"""
Unit tests for collection route handlers.

Tests verify that collection routes work correctly through the lambda handler entrypoint.
"""

import json

from src.entrypoint.api import lambda_handler


class TestCreateCollectionRoute:
    """Test suite for CreateCollectionRoute through lambda handler."""

    def test_create_collection_route_handler(self, mock_service_provider):
        """Test create collection route handler returns expected response."""
        event = {
            "resource": "/v1/collections",
            "path": "/v1/collections",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Create collection endpoint" in body["message"]


class TestListCollectionsRoute:
    """Test suite for ListCollectionsRoute through lambda handler."""

    def test_list_collections_route_handler(self, mock_service_provider):
        """Test list collections route handler returns expected response."""
        event = {
            "resource": "/v1/collections",
            "path": "/v1/collections",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "List collections endpoint" in body["message"]


class TestGetCollectionRoute:
    """Test suite for GetCollectionRoute through lambda handler."""

    def test_get_collection_route_handler(self, mock_service_provider):
        """Test get collection route handler returns expected response."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}",
            "path": f"/v1/collections/{collection_id}",
            "httpMethod": "GET",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Get collection endpoint" in body["message"]


class TestUpdateCollectionRoute:
    """Test suite for UpdateCollectionRoute through lambda handler."""

    def test_update_collection_route_handler(self, mock_service_provider):
        """Test update collection route handler returns expected response."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}",
            "path": f"/v1/collections/{collection_id}",
            "httpMethod": "PUT",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Update collection endpoint" in body["message"]


class TestDeleteCollectionRoute:
    """Test suite for DeleteCollectionRoute through lambda handler."""

    def test_delete_collection_route_handler(self, mock_service_provider):
        """Test delete collection route handler returns expected response."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}",
            "path": f"/v1/collections/{collection_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Delete collection endpoint" in body["message"]


class TestAddItemToCollectionRoute:
    """Test suite for AddItemToCollectionRoute through lambda handler."""

    def test_add_item_to_collection_route_handler(self, mock_service_provider):
        """Test add item to collection route handler returns expected response."""
        collection_id = "test-collection-123"
        event = {
            "resource": "/v1/collections/{collection_id}/items",
            "path": f"/v1/collections/{collection_id}/items",
            "httpMethod": "POST",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id},
            "body": json.dumps({}),
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Add item to collection endpoint" in body["message"]


class TestRemoveItemFromCollectionRoute:
    """Test suite for RemoveItemFromCollectionRoute through lambda handler."""

    def test_remove_item_from_collection_route_handler(self, mock_service_provider):
        """Test remove item from collection route handler returns expected response."""
        collection_id = "test-collection-123"
        item_id = "test-item-456"
        event = {
            "resource": "/v1/collections/{collection_id}/items/{item_id}",
            "path": f"/v1/collections/{collection_id}/items/{item_id}",
            "httpMethod": "DELETE",
            "headers": {"Content-Type": "application/json"},
            "pathParameters": {"collection_id": collection_id, "item_id": item_id},
            "requestContext": {"requestId": "test-request-id"},
        }

        response = lambda_handler(event, {}, mock_service_provider)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "Remove item from collection endpoint" in body["message"]
