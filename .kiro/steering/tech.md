---
inclusion: always
---

# Technology Stack & Development Guidelines

## Core Stack

**Infrastructure as Code**: AWS CDK with TypeScript
- Use CDK constructs for all AWS resource definitions
- Follow CDK best practices: use L2/L3 constructs over L1 when available
- Define stack outputs for cross-stack references
- Use CDK context for environment-specific configuration

**Backend**: AWS Lambda with Python 3.11+
- Use AWS Lambda Powertools for Python (structured logging, tracing, metrics)
- Keep Lambda functions focused and single-purpose
- Set appropriate timeout and memory configurations
- Use environment variables for configuration, never hardcode values

**API Layer**: AWS API Gateway (REST) + Smithy Model
- Define all APIs using Smithy model specifications
- Use RESTful conventions with proper HTTP verbs
- Implement API versioning from the start
- Generate API documentation from Smithy models

**Storage**: AWS S3 + DynamoDB
- S3: Enable server-side encryption, versioning, and lifecycle policies
- DynamoDB: Use single-table design patterns where appropriate
- Implement proper partition key design to avoid hot partitions
- Use GSIs for alternate query patterns

**Security**: AWS Cognito + SigV4
- Implement user authentication via Cognito with OIDC support
- Use scoped credentials to enforce user-level access control
- Never store unencrypted sensitive data

## Architecture Patterns

**Zero-Knowledge Design**
- All encryption/decryption MUST happen client-side
- Server never has access to encryption keys or unencrypted data
- Metadata, tags, and collections are encrypted before storage
- Use password-based key derivation for master keys

**Performance-First Approach**
- Use presigned S3 URLs for direct client-to-S3 uploads/downloads (bypass Lambda)
- Implement S3 multipart upload for files >5MB
- Enable S3 Transfer Acceleration for global users
- Use DynamoDB pagination for large result sets
- Create appropriate DynamoDB indexes for query optimization

**Serverless Best Practices**
- Lambda functions should be stateless
- Use Lambda layers for shared dependencies
- Implement proper error handling and retries
- Use dead letter queues for failed invocations

## Code Style & Conventions

**TypeScript (CDK)**
- Use strict TypeScript configuration
- Follow AWS CDK naming conventions (PascalCase for constructs)
- Use interfaces for construct props
- Add JSDoc comments for public APIs

**Python (Lambda)**
- Follow PEP 8 style guide
- Use type hints for all function signatures
- Use Pydantic models for request/response validation
- Implement proper exception handling with custom error types

**AWS Lambda Powertools Usage**
- Always use `@logger.inject_lambda_context` decorator for logging
- Use `@tracer.capture_method` for X-Ray tracing on key functions
- Use `@metrics.log_metrics` for CloudWatch custom metrics
- Use `APIGatewayRestResolver` for API Gateway event handling
- Validate inputs with `@validator` decorator and Pydantic models

Example Lambda handler structure:
```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()

@app.post("/resource")
@tracer.capture_method
def create_resource():
    # Handler logic
    pass

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
```

## Development Workflow

**CDK Development**
```bash
npm install              # Install dependencies
npm run build            # Compile TypeScript
cdk synth               # Generate CloudFormation
cdk diff                # Preview changes
cdk deploy              # Deploy to AWS
```

**Lambda Development**
```bash
pip install -r requirements.txt          # Install dependencies
python -m pytest                         # Run tests
python -m pytest --cov=lambda tests/     # Run with coverage
```

**Testing Requirements**
- Write unit tests for all Lambda functions
- Use moto for mocking AWS services in tests
- Aim for >80% code coverage
- Test error paths and edge cases

## Security Requirements

- Never log sensitive data (keys, passwords, PII)
- Use AWS Secrets Manager or Parameter Store for secrets
- Implement least-privilege IAM policies
- Enable CloudTrail logging for audit trails
- Use VPC endpoints for private AWS service access when needed
- Validate all inputs at API Gateway and Lambda layers

## Deployment Considerations

- Use CDK deployment stages (dev, staging, prod)
- Implement gradual Lambda deployments with aliases
- Use CloudWatch alarms for monitoring
- Set up X-Ray tracing for distributed debugging
- Configure appropriate Lambda reserved concurrency
- Implement proper backup and disaster recovery strategies
