---
inclusion: always
---

# Project Structure & Organization

## Directory Structure

```
cortex/
├── infrastructure/         # CDK stacks (TypeScript)
│   ├── lib/               # Stack definitions
│   │   ├── storage-stack.ts
│   │   ├── database-stack.ts
│   │   ├── auth-stack.ts
│   │   └── api-stack.ts
│   ├── bin/app.ts         # CDK entry point
│   ├── cdk.json
│   └── package.json
├── api/smithy/            # Smithy API models
├── lambda/                # Python Lambda handlers
│   ├── {feature}/        # One directory per Lambda
│   │   └── handler.py
│   ├── shared/           # Common utilities
│   │   ├── crypto.py
│   │   ├── auth.py
│   │   └── models.py
│   └── requirements.txt
├── tests/
│   ├── unit/
│   └── integration/
└── docs/
```

## File Naming & Location Rules

**When creating files, use these exact paths:**
- CDK stacks: `infrastructure/lib/{name}-stack.ts` (kebab-case)
- Lambda handlers: `lambda/{feature}/handler.py`
- Shared utilities: `lambda/shared/{purpose}.py`
- API models: `api/smithy/{service}.smithy`
- Tests: `tests/{unit|integration}/test_{module}.py`

**Naming conventions:**
- TypeScript: kebab-case files, PascalCase classes (`storage-stack.ts` → `StorageStack`)
- Python: snake_case for files and functions
- Smithy: kebab-case with namespace `com.cortex.{service}`

## Code Organization Patterns

**Lambda structure (handler → service → repository):**
- Keep `handler.py` thin - only event parsing and response formatting
- Business logic in separate service modules
- Data access in repository modules
- Shared code in `lambda/shared/`

**CDK organization:**
- One stack per AWS service grouping (storage, database, auth, api)
- Export stack outputs for cross-stack references
- Environment config in `cdk.json` context
- Reusable constructs in separate files

**API-first development:**
- Define all operations in Smithy models before implementation
- Version all APIs (`/v1/...`)
- Generate OpenAPI docs from Smithy

## Required Dependencies

**Python (Lambda):**
```
aws-lambda-powertools[all]>=2.0.0,<3.0.0
pydantic>=2.0
boto3  # Provided by Lambda runtime
```

**TypeScript (CDK):**
```json
{
  "dependencies": {
    "aws-cdk-lib": "^2.x.x",
    "constructs": "^10.x.x"
  }
}
```

## AWS Resource Naming

**Pattern:** `cortex-{env}-{resource-type}-{purpose}`

Examples:
- `cortex-prod-bucket-media`
- `cortex-dev-table-metadata`
- `cortex-staging-function-upload`

Environments: `dev`, `staging`, `prod`

## Architecture Constraints

**CRITICAL - Zero-Knowledge Rules:**
- Lambda functions NEVER receive unencrypted user data
- All encryption/decryption happens client-side only
- Use presigned S3 URLs for direct client-to-S3 transfers (bypass Lambda for data)
- Store metadata encrypted in DynamoDB

**Serverless-only:**
- No EC2, ECS, or containers
- Lambda for compute
- S3 and DynamoDB for storage
- API Gateway for HTTP

**Security boundaries:**
- Cognito identity-based IAM policies isolate user data
- S3 bucket policies enforce encryption at rest
- API Gateway validates JWT before Lambda invocation

## Standard Import Patterns

**Python Lambda:**
```python
import boto3
from botocore.exceptions import ClientError
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from shared.models import UploadRequest, UploadResponse
from shared.auth import validate_user
```

**TypeScript CDK:**
```typescript
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { Construct } from 'constructs';
```
