"""Lambda entrypoint for Cortex API. Uses Mangum to adapt FastAPI ASGI app for AWS Lambda."""

from src.environment.service_provider import lambda_entrypoint


@lambda_entrypoint
def handler(event, context, service_provider):
    return service_provider.handler(event, context)
