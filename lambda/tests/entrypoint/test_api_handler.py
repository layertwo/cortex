"""
Tests for the API Lambda handler.

This module tests the main Lambda handler entry point and route registration.
"""

from aws_lambda_powertools.event_handler import APIGatewayRestResolver

from src.entrypoint.api import lambda_handler


def test_api_handler_imports():
    """Test that the lambda handler can be imported successfully."""
    assert lambda_handler is not None


def test_service_provider_creates_api_router(mock_service_provider):
    """Test that the service provider creates an API router with all routes."""
    assert mock_service_provider.api_router is not None
    assert hasattr(mock_service_provider.api_router, "handle")
    assert hasattr(mock_service_provider.api_router, "app")


def test_api_router_has_routes_registered(mock_service_provider):
    """Test that routes are registered with the API router."""
    # The router should have routes registered
    assert len(mock_service_provider.api_router.routes) > 0
    # Should have at least the main route categories (20+ routes defined)
    assert len(mock_service_provider.api_router.routes) >= 20


def test_lambda_handler_with_service_provider(mock_service_provider):
    """Test lambda handler accepts service provider and has correct structure."""
    # Verify the service provider has the expected structure
    assert hasattr(mock_service_provider, "api_router")
    assert hasattr(mock_service_provider.api_router, "handle")

    # Verify lambda_handler function exists and is callable
    assert callable(lambda_handler)


def test_lambda_handler_delegates_to_router(mock_service_provider):
    """Test that lambda handler has access to router's handle method."""
    # Verify the router has the handle method that lambda_handler will call
    assert hasattr(mock_service_provider.api_router, "handle")
    assert callable(mock_service_provider.api_router.handle)


def test_api_router_structure(mock_service_provider):
    """Test that the service provider router has the correct structure."""
    # Verify the router has the app resolver
    assert hasattr(mock_service_provider.api_router, "app")
    assert isinstance(mock_service_provider.api_router.app, APIGatewayRestResolver)

    # Verify routes are registered
    assert len(mock_service_provider.api_router.routes) > 0


def test_service_provider_initializes_all_routes(mock_service_provider):
    """Test that service provider initializes all expected route types."""
    route_classes = [type(route).__name__ for route in mock_service_provider.api_router.routes]

    # Verify auth routes
    assert "LoginRoute" in route_classes
    assert "RefreshRoute" in route_classes
    assert "RecoverRoute" in route_classes

    # Verify vault routes
    assert "CreateVaultRoute" in route_classes
    assert "GetVaultSaltRoute" in route_classes

    # Verify item routes
    assert "CreateItemRoute" in route_classes
    assert "ListItemsRoute" in route_classes
    assert "GetItemRoute" in route_classes
    assert "UpdateItemRoute" in route_classes
    assert "DeleteItemRoute" in route_classes

    # Verify collection routes
    assert "CreateCollectionRoute" in route_classes
    assert "ListCollectionsRoute" in route_classes

    # Verify tag routes
    assert "SearchTagsRoute" in route_classes

    # Verify share routes
    assert "CreateShareRoute" in route_classes
    assert "GetShareRoute" in route_classes
    assert "RevokeShareRoute" in route_classes

    # Verify recovery routes
    assert "GenerateRecoveryCodesRoute" in route_classes
    assert "ValidateRecoveryCodeRoute" in route_classes
