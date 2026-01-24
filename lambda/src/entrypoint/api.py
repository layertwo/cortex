"""
API Lambda entrypoint for Cortex API.

This module provides the Lambda handler entry point that uses the
service provider to initialize and route requests.
"""

from typing import Optional

from aws_lambda_powertools.utilities.typing import LambdaContext

from src.environment.service_provider import ServiceProvider


def lambda_handler(
    event: dict, context: LambdaContext, service_provider: Optional[ServiceProvider] = None
) -> dict:
    """
    Cortex API Lambda handler.

    This is the main entry point for all API requests. It uses the service
    provider pattern to initialize dependencies and route requests.

    Args:
        event: API Gateway event dictionary
        context: Lambda context object
        service_provider: Optional ServiceProvider for dependency injection (used in tests)

    Returns:
        API Gateway response dictionary
    """
    if service_provider is None:  # pragma: nocover
        service_provider = ServiceProvider()

    return service_provider.api_router.handle(event, context)
