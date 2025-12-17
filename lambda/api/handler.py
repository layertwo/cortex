"""
Main Lambda handler for Cortex Backup API.

This handler uses AWS Lambda Powertools APIGatewayRestResolver to route
all API requests to appropriate domain-specific route handlers.
"""

from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

# Initialize Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# Initialize API Gateway REST resolver
app = APIGatewayRestResolver()

# Route modules will be imported and registered in later tasks
# from routes import auth, vaults, media, collections, tags, shares, recovery


@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    """
    Main Lambda handler function.
    
    Args:
        event: API Gateway event
        context: Lambda context
        
    Returns:
        API Gateway response
    """
    return app.resolve(event, context)
