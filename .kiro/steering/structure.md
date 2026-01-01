---
inclusion: always
---

# Project Structure & Organization

## Directory Structure

```
cortex/
├── cdk /                  # CDK stacks (TypeScript)
│   ├── lib/               # Stack definitions
│   │   ├── storage-stack.ts
│   │   ├── database-stack.ts
│   │   ├── auth-stack.ts
│   │   └── api-stack.ts
│   ├── bin/app.ts         # CDK entry point
│   ├── cdk.json
│   └── package.json
├── api/smithy/            # Smithy API models
│   └── cortex-backup.smithy
├── lambda/                # Python Lambda handlers
│   ├── api/              # Main API handler using Lambda Powertools
│   │   ├── handler.py    # Entry point with APIGatewayRestResolver
│   │   ├── routes/       # Route handlers organized by domain
│   │   │   ├── auth.py       # Authentication routes
│   │   │   ├── vaults.py     # Vault management routes
│   │   │   ├── media.py      # Media upload/download/list routes
│   │   │   ├── collections.py # Collection CRUD routes
│   │   │   ├── tags.py       # Tag search routes
│   │   │   ├── shares.py     # File sharing routes
│   │   │   └── recovery.py   # Account recovery routes
│   │   └── services/     # Business logic layer
│   │       ├── media_service.py
│   │       ├── collection_service.py
│   │       ├── vault_service.py
│   │       └── share_service.py
│   ├── shared/           # Common utilities
│   │   ├── crypto.py
│   │   ├── auth.py
│   │   ├── models.py
│   │   ├── errors.py
│   │   └── repository.py  # DynamoDB/S3 access layer
│   └── requirements.txt
├── client/                # Client-side encryption library
│   ├── src/
│   │   ├── encryption.ts  # ChaCha20-Poly1305 implementation
│   │   ├── key-management.ts  # Argon2id, HKDF, key derivation
│   │   ├── password-validation.ts  # Strength and breach checking
│   │   ├── sharing.ts     # Share key generation
│   │   └── content-analysis.ts  # Optional ML tagging
│   └── package.json
├── tests/
│   ├── unit/
│   ├── integration/
│   └── property/          # Property-based tests
└── docs/
```

## File Naming & Location Rules

**When creating files, use these exact paths:**
- CDK stacks: `cdk/lib/{name}-stack.ts` (kebab-case)
- Lambda handlers: `lambda/{feature}/handler.py`
- Shared utilities: `lambda/shared/{purpose}.py`
- API models: `api/smithy/{service}.smithy`
- Tests: `tests/{unit|integration}/test_{module}.py`

**Naming conventions:**
- TypeScript: kebab-case files, PascalCase classes (`storage-stack.ts` → `StorageStack`)
- Python: snake_case for files and functions
- Smithy: kebab-case with namespace `com.cortex.{service}`

## Code Organization Patterns

**Lambda structure (handler → routes → services → repository):**
- Single Lambda function using AWS Lambda Powertools `APIGatewayRestResolver`
- `handler.py` - Entry point with resolver setup and route registration
- `routes/` - Route handlers organized by domain (auth, vaults, media, collections, tags, shares, recovery)
- `services/` - Business logic layer (media_service, collection_service, vault_service, share_service)
- `shared/repository.py` - Data access layer for DynamoDB and S3
- Keep route handlers thin - delegate to service layer
- Shared code in `lambda/shared/`

**Benefits of single Lambda with APIGatewayRestResolver:**
- Reduced cold start overhead (shared Lambda container across routes)
- Simplified deployment (single function to deploy)
- Easier code sharing between routes
- Lower AWS costs (fewer Lambda functions to manage)
- Built-in routing with type-safe path parameters
- Automatic OpenAPI schema generation
- Consistent error handling across all routes

**CDK organization:**
- One stack per AWS service grouping (storage, database, auth, api)
- Single Lambda function for all API routes (uses APIGatewayRestResolver)
- API Gateway configured with proxy integration to Lambda
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
hypothesis>=6.0  # Property-based testing
pytest>=7.0
pytest-cov>=4.0
moto>=4.0  # AWS service mocking
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

**TypeScript/JavaScript (Client):**
```json
{
  "dependencies": {
    "@noble/ciphers": "^0.4.0",  // ChaCha20-Poly1305
    "@noble/hashes": "^1.3.0",   // SHA-256, HMAC
    "argon2-browser": "^1.18.0", // Argon2id for browser
    "bip39": "^3.1.0"            // BIP39 mnemonic generation
  },
  "devDependencies": {
    "fast-check": "^3.0.0"       // Property-based testing
  }
}
```

## AWS Resource Naming

**Pattern:** `cortex-{env}-{resource-type}-{purpose}`

Examples:
- `cortex-prod-bucket-files`
- `cortex-dev-table-users`
- `cortex-dev-table-vaults`
- `cortex-dev-table-files`
- `cortex-dev-table-collections`
- `cortex-dev-table-file-collection-associations`
- `cortex-dev-table-shares`
- `cortex-dev-table-account-recovery`
- `cortex-staging-function-api` (single Lambda handles all routes)
- `cortex-prod-api-gateway`

Environments: `dev`, `staging`, `prod`

## Architecture Constraints

**CRITICAL - Zero-Knowledge Rules:**
- Lambda functions NEVER receive unencrypted user data
- All encryption/decryption happens client-side only
- Use presigned S3 URLs for direct client-to-S3 transfers (bypass Lambda for data)
- Store metadata encrypted in DynamoDB
- Vault password and vault keys NEVER transmitted to server
- Vault recovery keys NEVER transmitted to or stored by server
- Share keys embedded in URL fragments (never sent to server)

**Serverless-only:**
- No EC2, ECS, or containers
- Lambda for compute (Python 3.11+)
- S3 and DynamoDB for storage
- API Gateway for HTTP
- Cognito for authentication

**Security boundaries:**
- Cognito handles account password authentication only
- Lambda generates scoped presigned URLs (no per-user IAM policies)
- S3 bucket policies enforce encryption at rest (AES-256)
- API Gateway validates SigV4 signatures before Lambda invocation
- Lambda enforces user isolation for all data operations

## DynamoDB Schema Patterns

**Users Table:**
- PK: `USER#{userId}`, SK: `PROFILE`
- Stores: userId, cognitoId, email, timestamps

**Vaults Table:**
- PK: `USER#{userId}`, SK: `VAULT#{vaultId}`
- Stores: vaultId, userId, vaultSalt (binary, non-secret), timestamps

**Files Table:**
- PK: `VAULT#{vaultId}`, SK: `FILE#{fileId}`
- Stores: fileId, vaultId, userId, s3Key, encryptedMetadata (binary), encryptedTags (list<binary>), uploadedAt, sizeBytes
- GSI1: PK: `VAULT#{vaultId}#TAG#{encryptedTag}`, SK: `FILE#{fileId}` (for tag-based queries)

**Collections Table:**
- PK: `VAULT#{vaultId}`, SK: `COLLECTION#{collectionId}`
- Stores: collectionId, vaultId, userId, encryptedMetadata (binary), timestamps, itemCount

**File-Collection Association Table:**
- PK: `COLLECTION#{collectionId}`, SK: `FILE#{fileId}`
- GSI1: PK: `FILE#{fileId}`, SK: `COLLECTION#{collectionId}` (reverse lookup)
- Stores: collectionId, fileId, vaultId, userId, addedAt

**Shares Table:**
- PK: `SHARE#{shareId}`, SK: `METADATA`
- Stores: shareId, fileId, vaultId, userId, createdAt, expiresAt, isPasswordProtected, isRevoked, accessCount, lastAccessedAt
- Note: Share key NOT stored (embedded in URL)

**Account Recovery Table:**
- PK: `USER#{userId}`, SK: `RECOVERY#{codeHash}`
- Stores: userId, codeHash (SHA-256), createdAt, usedAt, isValid

## S3 Bucket Structure

**Object Key Pattern:**
```
vaults/{vaultId}/files/{fileId}/{timestamp}-{random}
```

**Bucket Configuration:**
- Server-side encryption: AES-256
- Versioning: Enabled
- Lifecycle policies: Optional Glacier transition after 90 days
- Transfer acceleration: Enabled
- CORS: Configured for direct client uploads
- Multipart upload: 5MB minimum part size, 10,000 max parts

**Presigned URL Configuration:**
- Upload URLs: 15-minute expiration, PUT only, scoped to specific object key
- Download URLs: 15-minute expiration, GET only, scoped to specific object key

## Standard Import Patterns

**Python Lambda (handler.py):**
```python
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from routes import auth, vaults, media, collections, tags, shares, recovery

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()

# Register route modules
auth.register_routes(app)
vaults.register_routes(app)
media.register_routes(app)
collections.register_routes(app)
tags.register_routes(app)
shares.register_routes(app)
recovery.register_routes(app)

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
```

**Python Lambda (route module example - routes/media.py):**
```python
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from services.media_service import MediaService
from shared.models import UploadRequest, UploadResponse
from shared.auth import get_user_from_context

logger = Logger(child=True)
tracer = Tracer()

def register_routes(app: APIGatewayRestResolver):
    @app.post("/v1/media/upload/init")
    @tracer.capture_method
    def init_upload():
        user_id = get_user_from_context(app.current_event)
        body = app.current_event.json_body
        request = UploadRequest(**body)
        
        service = MediaService()
        response = service.initiate_upload(user_id, request)
        
        return response.dict()
    
    @app.get("/v1/media/list")
    @tracer.capture_method
    def list_media():
        user_id = get_user_from_context(app.current_event)
        page_size = app.current_event.query_string_parameters.get("page_size", 50)
        next_token = app.current_event.query_string_parameters.get("next_token")
        
        service = MediaService()
        response = service.list_media(user_id, page_size, next_token)
        
        return response.dict()
```

**TypeScript CDK:**
```typescript
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import { Construct } from 'constructs';

// Example: Single Lambda with API Gateway proxy integration
const apiHandler = new lambda.Function(this, 'ApiHandler', {
  runtime: lambda.Runtime.PYTHON_3_11,
  handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset('lambda/api'),
  environment: {
    USERS_TABLE: usersTable.tableName,
    VAULTS_TABLE: vaultsTable.tableName,
    FILES_TABLE: filesTable.tableName,
    // ... other table names
  },
  timeout: cdk.Duration.seconds(30),
  memorySize: 512,
});

// API Gateway with proxy integration
const api = new apigateway.RestApi(this, 'CortexApi', {
  restApiName: 'Cortex Backup API',
  deployOptions: {
    stageName: 'v1',
    tracingEnabled: true,
  },
});

api.root.addProxy({
  defaultIntegration: new apigateway.LambdaIntegration(apiHandler),
  anyMethod: true,
});
```
