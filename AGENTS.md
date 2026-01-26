# Cortex: Zero-Knowledge Media Backup System

Cortex is a privacy-first photo and video backup solution where all encryption happens in the React frontend. The backend never has access to unencrypted user data, metadata, or encryption keys.

## Product Model

**B2C Single-User Architecture:**
- Individual users, not organizations or teams
- One user = one vault (personal backup)
- No multi-tenancy or team collaboration features
- Simplified security model focused on personal data protection
- Usage tracking and quotas per individual user

## Critical Architecture Constraints

**Zero-Knowledge Enforcement:**
- Backend MUST NEVER receive or process unencrypted user data
- All encryption/decryption operations happen exclusively in the React frontend
- Metadata (filenames, dates, locations), tags, and collections are encrypted before transmission
- Server only stores encrypted blobs and cannot decrypt them

**Data Flow Pattern:**
- React frontend encrypts data → Frontend uploads directly to S3 via presigned URL → Server stores encrypted metadata in DynamoDB
- React frontend requests presigned URL → Frontend downloads from S3 → Frontend decrypts locally
- Lambda functions only handle presigned URL generation and encrypted metadata operations

**Two-Password Security Model:**
- **Account Password**: Used for AWS Cognito authentication, can be changed without re-encrypting vault data
- **Vault Password**: Used exclusively for deriving vault encryption keys, never transmitted to server
- Separation allows flexible credential management without expensive re-encryption
- Vault password + server-stored vault salt → Argon2id → Vault master key (256-bit)
- HKDF derives multiple keys from vault master key: data encryption key, metadata encryption key, share key derivation key

**Key Management:**
- Vault master key derived from vault password using Argon2id (64MB memory, 3 iterations, 4 parallelism)
- Vault salt stored on server (non-secret, enables multi-device key derivation)
- Keys never transmitted to or stored on backend
- Multi-device support via vault password + vault salt (derive same keys on any device)
- Vault recovery key (24-word BIP39 mnemonic) enables complete offline vault recovery without server dependency
- Account recovery codes (10 per user) enable account password reset
- Automatic key rotation every 90 days with background re-encryption

## Core Stack

**Infrastructure as Code**: AWS CDK with TypeScript
- Use CDK constructs for all AWS resource definitions
- Follow CDK best practices: use L2/L3 constructs over L1 when available
- Define stack outputs for cross-stack references
- Use CDK context for environment-specific configuration

**Backend**: AWS Lambda with Python 3.11+
- Use AWS Lambda Powertools for Python (structured logging, tracing, metrics)
- Single Lambda function using `APIGatewayRestResolver` for all API routes
- Route handlers organized by domain in separate modules
- Business logic in service layer, data access in repository layer
- Set appropriate timeout and memory configurations
- Use environment variables for configuration, never hardcode values

**API Layer**: AWS API Gateway (REST) + Smithy Model
- Define all APIs using Smithy model specifications
- Use RESTful conventions with proper HTTP verbs
- Implement API versioning from the start (URI versioning: `/v1/...`)
- Generate API documentation from Smithy models (OpenAPI 3.0, client SDKs)
- Current version: v1

**Storage**: AWS S3 + DynamoDB
- S3: Enable server-side encryption (AES-256), versioning, and lifecycle policies
- S3: Configure multipart upload (5MB min part size), transfer acceleration
- DynamoDB: Multiple tables with specific access patterns (Users, Vaults, Files, Collections, Shares, Recovery)
- DynamoDB: Use composite keys (PK/SK) and GSIs for query optimization
- Implement proper partition key design to avoid hot partitions

**Security**: AWS Cognito + SigV4
- Cognito handles account password authentication only (not vault password)
- Custom authentication flow for account recovery codes
- SigV4 request signing for all API calls
- Lambda generates scoped presigned URLs (no per-user IAM policies needed)
- Never store unencrypted sensitive data

**Frontend Encryption**: ChaCha20-Poly1305
- Library: @noble/ciphers (React/browser), cryptography (Python for testing)
- Key size: 256 bits
- Nonce size: 96 bits (12 bytes, random per operation)
- Tag size: 128 bits (16 bytes, authenticated encryption)

**Key Derivation**: Argon2id + HKDF
- Argon2id: 64MB memory, 3 iterations, 4 parallelism
- Input: vault password + vault salt (16 bytes)
- Output: 256-bit vault master key
- HKDF derives multiple keys from vault master key:
  - Data encryption key (context: "cortex-data-encryption-v1")
  - Metadata encryption key (context: "cortex-metadata-encryption-v1")
  - Share key derivation key (context: "cortex-share-key-derivation-v1")

**Tag Encryption**: Deterministic HMAC-SHA256 with vault-scoped salting and padding
- Enables server-side exact match without revealing plaintext
- Vault-scoped salting prevents cross-vault tag correlation
- Fixed-length padding (64 bytes) prevents length-based analysis
- Consistent output for same tag within same vault (searchability)
- Tags normalized to lowercase before encryption
- Security enhancements:
  - Same tag in different vaults produces different encrypted values (vault isolation)
  - All encrypted tags have same length regardless of input (padding)
  - Input validation prevents empty vaultId attacks
- Trade-offs remain:
  - Frequency analysis still possible within single vault
  - Dictionary attacks possible if tag space is small
  - No protection against known-plaintext attacks

## SaaS Operational Patterns

**Usage Metering & Monitoring:**
- Track storage usage per user (total bytes stored)
- Track API call counts per user per billing period
- Track file upload/download operations
- Publish usage events to EventBridge for analytics
- Store aggregated usage metrics in DynamoDB
- Display usage dashboard to users (storage used, API calls, etc.)
- No payment processing initially - monitoring only

**Quota Management:**
- Define storage quotas per user (e.g., 5GB free tier, 100GB paid tier)
- Define API rate limits per user (requests per minute/hour)
- Check quotas before expensive operations (file uploads, bulk operations)
- Return 429 (Too Many Requests) with upgrade message when quota exceeded
- Graceful degradation: read-only mode when storage quota reached
- Cache quota limits in Lambda memory for performance

**Feature Flags:**
- Per-user feature flag system for gradual rollout
- Flags stored in DynamoDB or environment variables
- Check flags before enabling new features
- Support A/B testing and beta user groups
- Common flags: `enable_collections`, `enable_sharing`, `enable_ml_tagging`
- Default to safe/stable behavior when flag not found

**Health Checks & Monitoring:**
- `/health` endpoint for service health checks
- Return service status, version, and dependency health
- Monitor DynamoDB, S3, and Cognito availability
- User-aware logging with user_id context (never log sensitive data)
- CloudWatch metrics for: API latency, error rates, storage usage
- X-Ray tracing for request flow analysis

## Directory Structure

```
cortex/
├── cdk/                   # CDK stacks (TypeScript)
│   ├── lib/               # Stack definitions
│   │   ├── stacks/
│   │   │   ├── auth.ts
│   │   │   ├── service.ts
│   │   │   └── monitoring.ts  # CloudWatch dashboards, alarms
│   │   ├── app.ts
│   │   └── config.ts
│   ├── bin/app.ts         # CDK entry point
│   ├── cdk.json
│   └── package.json
├── smithy/                # Smithy API models (modular structure)
│   ├── models/
│   │   ├── main.smithy
│   │   ├── common.smithy
│   │   ├── errors.smithy
│   │   ├── auth/
│   │   ├── vault/
│   │   ├── item/
│   │   ├── collection/
│   │   ├── tag/
│   │   ├── share/
│   │   ├── recovery/
│   │   └── usage/         # Usage tracking models
│   └── smithy-build.json
├── lambda/                # Python Lambda handlers
│   ├── src/
│   │   ├── api/          # Main API handler using Lambda Powertools
│   │   │   ├── handler.py    # Entry point with APIGatewayRestResolver
│   │   │   ├── routes/       # Route handlers organized by domain
│   │   │   │   ├── auth.py
│   │   │   │   ├── vaults.py
│   │   │   │   ├── items.py
│   │   │   │   ├── collections.py
│   │   │   │   ├── tags.py
│   │   │   │   ├── shares.py
│   │   │   │   ├── recovery.py
│   │   │   │   ├── usage.py      # Usage tracking routes
│   │   │   │   └── health.py     # Health check routes
│   │   │   └── services/     # Business logic layer
│   │   │       ├── item_service.py
│   │   │       ├── collection_service.py
│   │   │       ├── vault_service.py
│   │   │       ├── share_service.py
│   │   │       └── usage_service.py  # Usage tracking logic
│   │   └── shared/           # Common utilities
│   │       ├── crypto.py
│   │       ├── auth.py
│   │       ├── models.py
│   │       ├── errors.py
│   │       ├── repository.py
│   │       ├── features.py       # Feature flag utilities
│   │       ├── usage.py          # Usage metering utilities
│   │       └── quota.py          # Quota enforcement utilities
│   ├── requirements.txt
│   └── requirements-dev.txt
├── packages/              # Monorepo packages (npm workspaces)
│   ├── encryption/        # @cortex/encryption - Standalone encryption library
│   │   ├── src/
│   │   │   ├── lib/
│   │   │   │   ├── encryption.ts     # ChaCha20-Poly1305
│   │   │   │   ├── key-management.ts # Argon2id, HKDF
│   │   │   │   ├── password-validation.ts
│   │   │   │   └── sharing.ts
│   │   │   └── index.ts
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   └── property/
│   │   ├── package.json
│   │   └── tsconfig.json
│   └── web/               # @cortex/web - React web application
│       ├── src/
│       │   ├── components/    # React components
│       │   ├── hooks/         # React hooks
│       │   ├── pages/         # Page components
│       │   ├── api/           # API client
│       │   ├── App.tsx
│       │   └── main.tsx
│       ├── public/
│       ├── index.html
│       ├── package.json
│       ├── tsconfig.json
│       └── vite.config.ts
├── package.json           # Root workspace configuration
└── docs/
```

## File Naming & Location Rules

**When creating files, use these exact paths:**
- CDK stacks: `cdk/lib/{name}-stack.ts` (kebab-case)
- Lambda handlers: `lambda/{feature}/handler.py`
- Shared utilities: `lambda/shared/{purpose}.py`
- API models: `smithy/models/{domain}/{resource}.smithy`
- Encryption library: `packages/encryption/src/lib/{module}.ts`
- Web app components: `packages/web/src/components/{Component}.tsx`
- Tests: `packages/{package}/tests/{unit|integration|property}/test_{module}.{ts|py}`

**Naming conventions:**
- TypeScript: kebab-case files, PascalCase classes (`storage-stack.ts` → `StorageStack`)
- Python: snake_case for files and functions
- Smithy: kebab-case with namespace `com.cortex.{service}`
- React components: PascalCase files and components (`Button.tsx` → `Button`)

## Code Organization Patterns

**Lambda structure (handler → routes → services → repository):**
- Single Lambda function using AWS Lambda Powertools `APIGatewayRestResolver`
- `handler.py` - Entry point with resolver setup and route registration
- `routes/` - Route handlers organized by domain (auth, vaults, items, collections, tags, shares, recovery)
- `services/` - Business logic layer (item_service, collection_service, vault_service, share_service)
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

## Frontend Architecture (Monorepo)

**Monorepo Structure:**
- npm workspaces for package management
- `@cortex/encryption` - Standalone encryption library (reusable across platforms)
- `@cortex/web` - React web application (imports encryption library)

**Technology Stack:**
- React 18+ with TypeScript (strict mode)
- Vite for build tooling and dev server
- Tailwind CSS for styling (to be added)
- `@cortex/encryption` library for all cryptographic operations

**Encryption Library (@cortex/encryption):**
```
packages/encryption/src/
├── lib/
│   ├── encryption.ts          # ChaCha20-Poly1305 core
│   ├── key-management.ts      # Argon2id, HKDF
│   ├── password-validation.ts # Password strength, breach check
│   └── sharing.ts             # Share key derivation
├── index.ts                   # Public API exports
└── tests/
    ├── unit/                  # Unit tests
    └── property/              # Property-based tests (fast-check)
```

**Web Application (@cortex/web):**
```
packages/web/src/
├── components/        # Reusable UI components
│   ├── auth/         # Login, signup, recovery
│   ├── vault/        # Vault management
│   ├── files/        # File upload, list, preview
│   ├── collections/  # Collection management
│   └── common/       # Buttons, modals, etc.
├── hooks/            # Custom React hooks
│   ├── useAuth.ts
│   ├── useVault.ts
│   ├── useUsage.ts
│   └── useFeatureFlag.ts
├── api/              # API client
│   └── client.ts
├── pages/            # Page components
│   ├── Login.tsx
│   ├── Dashboard.tsx
│   ├── Files.tsx
│   └── Settings.tsx
├── App.tsx
└── main.tsx
```

**Encryption Flow:**
1. User enters vault password in React frontend (never sent to server)
2. React frontend uses `@cortex/encryption` to derive vault master key (Argon2id + vault salt)
3. React frontend uses `@cortex/encryption` to derive encryption keys (HKDF)
4. React frontend uses `@cortex/encryption` to encrypt file/metadata (ChaCha20-Poly1305)
5. React frontend uploads encrypted data to S3 via presigned URL
6. React frontend stores encrypted metadata via API

**State Management:**
- React Context for auth state and vault keys (in memory only)
- Local state for UI components
- No global state library needed initially

**Security Considerations:**
- React frontend never persists vault password or derived keys
- React frontend clears sensitive data from memory on logout
- `@cortex/encryption` uses secure random number generation for nonces
- React frontend validates all user inputs before encryption

**Development Workflow:**
- `npm run dev:web` - Start Vite dev server for web app
- `npm run dev:encryption` - Watch mode for encryption library
- Web app automatically picks up encryption library changes via workspace linking
- Both packages can be developed simultaneously

## Required Dependencies

**Python (Lambda):**
```
aws-lambda-powertools[all]>=2.0.0,<3.0.0
pydantic>=2.0
boto3  # Provided by Lambda runtime
hypothesis>=6.0  # Property-based testing
pytest>=7.0
pytest-cov>=4.0
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

**TypeScript/JavaScript (Encryption Library - @cortex/encryption):**
```json
{
  "dependencies": {
    "@noble/ciphers": "^0.4.0",  // ChaCha20-Poly1305
    "@noble/hashes": "^1.3.0",   // SHA-256, HMAC
    "argon2-browser": "^1.18.0", // Argon2id for browser
    "bip39": "^3.1.0"            // BIP39 mnemonic generation
  },
  "devDependencies": {
    "@types/node": "^20.x.x",
    "typescript": "^5.x.x",
    "jest": "^29.x.x",
    "ts-jest": "^29.x.x",
    "fast-check": "^3.0.0"       // Property-based testing
  }
}
```

**TypeScript/JavaScript (Web App - @cortex/web):**
```json
{
  "dependencies": {
    "@cortex/encryption": "workspace:*",  // Local workspace dependency
    "react": "^18.x.x",
    "react-dom": "^18.x.x"
  },
  "devDependencies": {
    "@types/react": "^18.x.x",
    "@types/react-dom": "^18.x.x",
    "@vitejs/plugin-react": "^4.x.x",
    "typescript": "^5.x.x",
    "vite": "^5.x.x",
    "vitest": "^1.x.x"
  }
}
```

## AWS Resource Naming

**Pattern:** `cortex-{env}-{resource-type}-{purpose}`

Examples:
- `cortex-prod-bucket-files`
- `cortex-dev-table-data` (single table for users, vaults, files, collections, usage, features)
- `cortex-dev-table-shares` (separate for anonymous access)
- `cortex-staging-function-api` (single Lambda handles all routes)
- `cortex-prod-api-gateway`
- `cortex-prod-eventbus-usage` (for usage event tracking)

Environments: `dev`, `staging`, `prod`

**Note:** Using single-table design for main data (users, vaults, files, collections, usage tracking, feature flags) with separate shares table for security isolation.

## DynamoDB Schema Patterns

**Users Table:**
- PK: `USER#{userId}`, SK: `PROFILE`
- Stores: userId, cognitoId, email, timestamps, storageQuotaBytes, apiRateLimit

**Vaults Table:**
- PK: `USER#{userId}`, SK: `VAULT#{vaultId}`
- Stores: vaultId, userId, vaultSalt (binary, non-secret), timestamps

**Files Table:**
- PK: `VAULT#{vaultId}`, SK: `FILE#{fileId}`
- Stores: fileId, vaultId, userId, s3Key, encryptedMetadata (binary), encryptedTags (list<binary>), uploadedAt, sizeBytes, upload_status (PENDING/COMPLETE), ttl (Unix epoch, for PENDING uploads only)
- GSI1: PK: `VAULT#{vaultId}#TAG#{encryptedTag}`, SK: `FILE#{fileId}` (for tag-based queries)
- TTL: Pending uploads auto-expire after 48 hours to prevent data inconsistency from failed/abandoned uploads

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

**Usage Tracking Table:**
- PK: `USER#{userId}`, SK: `USAGE#{period}` (e.g., USAGE#2024-01)
- Stores: userId, period, storageBytes, apiCalls, uploadsCount, downloadsCount, lastUpdated
- TTL: Auto-delete after 13 months (keep 1 year of history)

**Feature Flags Table:**
- PK: `USER#{userId}`, SK: `FEATURE#{featureName}`
- Stores: userId, featureName, enabled (boolean), enabledAt
- Alternative: Store in environment variables for global flags

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
from routes import auth, vaults, items, collections, tags, shares, recovery, usage, health

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()

# Register route modules
auth.register_routes(app)
vaults.register_routes(app)
items.register_routes(app)
collections.register_routes(app)
tags.register_routes(app)
shares.register_routes(app)
recovery.register_routes(app)
usage.register_routes(app)
health.register_routes(app)

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event: dict, context: LambdaContext) -> dict:
    return app.resolve(event, context)
```

**Python Lambda (route module with usage tracking):**
```python
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from services.item_service import ItemService
from shared.models import CreateItemRequest, CreateItemResponse
from shared.auth import get_user_from_context
from shared.usage import track_usage, UsageEventType
from shared.quota import check_quota, QuotaType

logger = Logger(child=True)
tracer = Tracer()

def register_routes(app: APIGatewayRestResolver):
    @app.post("/v1/items/upload/init")
    @tracer.capture_method
    def initiate_upload():
        user_id = get_user_from_context(app.current_event)
        body = app.current_event.json_body
        request = CreateItemRequest(**body)
        
        # Check storage quota before allowing upload
        check_quota(user_id, QuotaType.STORAGE, request.size_bytes)
        
        service = ItemService()
        response = service.initiate_upload(user_id, request)
        
        # Track usage event
        track_usage(user_id, UsageEventType.FILE_UPLOAD_INITIATED, {
            'file_size': request.size_bytes
        })
        
        return response.dict()
```

**Python Lambda (feature flag usage):**
```python
from shared.features import is_feature_enabled, FeatureFlag

def create_collection():
    user_id = get_user_from_context(app.current_event)
    
    # Check if collections feature is enabled for user
    if not is_feature_enabled(user_id, FeatureFlag.COLLECTIONS):
        return {
            'statusCode': 403,
            'body': {'error': 'Collections feature not available'}
        }
    
    # Proceed with collection creation
    service = CollectionService()
    response = service.create_collection(user_id, request)
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
- Single Lambda function handles all API routes using `APIGatewayRestResolver`
- Always use `@logger.inject_lambda_context` decorator on lambda_handler
- Use `@tracer.capture_method` for X-Ray tracing on route handlers and service methods
- Use `@metrics.log_metrics` for CloudWatch custom metrics
- Validate inputs with Pydantic models
- Organize routes by domain in separate modules

**Pydantic Validation Error Handling Pattern:**
```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from pydantic import ValidationError as PydanticValidationError
from src.shared.models import CreateItemRequest
from src.shared.errors import ValidationError  # Custom validation error

@app.post("/v1/items")
def handle():
    try:
        # Parse and validate request
        body = app.current_event.json_body
        request = CreateItemRequest(**body)
        
        # Process request...
        
    except PydanticValidationError as e:
        # Catch Pydantic validation errors BEFORE custom ValidationError
        logger.warning("Request validation failed", extra={"errors": e.errors()})
        return Response(
            status_code=400,
            content_type="application/json",
            body={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "Invalid request format",
                }
            },
        )
    
    except ValidationError as e:
        # Handle custom validation errors
        logger.warning("Validation failed", extra={"error": str(e)})
        return Response(
            status_code=400,
            content_type="application/json",
            body={"error": {"code": "INVALID_REQUEST", "message": str(e)}},
        )
```

**Key Points:**
- Always catch `PydanticValidationError` explicitly before custom `ValidationError`
- Import as `from pydantic import ValidationError as PydanticValidationError` to avoid naming conflicts
- Return sanitized error messages to prevent exposing internal validation details
- Log full error details server-side for debugging (use `e.errors()` for structured logging)
- Use Lambda Powertools `Response` object for consistent error formatting

## Security Requirements

- Never log sensitive data (keys, passwords, PII, encrypted payloads)
- Log with user context: user IDs, vault IDs, timestamps, operation types, error codes, performance metrics
- Never log: vault password, vault keys, 24-word vault recovery keys, share keys, account recovery codes
- Use AWS Secrets Manager or Parameter Store for secrets
- Implement least-privilege IAM policies for Lambda execution roles
- No per-user IAM policies (use scoped presigned URLs instead)
- Enable CloudTrail logging for audit trails
- Use VPC endpoints for private AWS service access when needed
- Validate all inputs at API Gateway and Lambda layers
- Sanitize error messages to prevent information leakage

**Authorization Pattern (CRITICAL - OWASP A01:2021):**
All endpoints that accept `vault_id` as a parameter MUST verify vault ownership before processing:
```python
# REQUIRED: Verify vault ownership before any vault operations
if not self.vault_service.vault_exists(user_id, vault_id):
    logger.warning(
        "Vault access denied - user does not own vault",
        extra={"user_id": user_id, "vault_id": vault_id, "operation": "operation_name"}
    )
    return Response(
        status_code=403,
        content_type="application/json",
        body={
            "error": {
                "code": "AUTHORIZATION_FAILED",
                "message": "Access denied to vault",
            }
        },
    )
```

This prevents broken access control vulnerabilities where users could access or modify data in vaults they don't own. The check must happen at the route layer before calling service methods.

**User-Aware Logging Pattern:**
```python
logger.info("File uploaded", extra={
    "user_id": user_id,
    "vault_id": vault_id,
    "file_size": size_bytes,
    "operation": "file_upload"
})
```

**Password Security:**
- Minimum 12 characters
- Require: uppercase, lowercase, numbers, special characters
- Breach detection via Have I Been Pwned API (k-anonymity model)
- React frontend performs SHA-1 hash, sends first 5 characters to API
- Check full hash against returned list locally
- Reject any password found in breach database

**Recovery Security:**
- Account recovery codes: 10 per user, 16 characters, format: XXXX-XXXX-XXXX-XXXX
- Codes hashed with SHA-256 before server storage
- One-time use (invalidated after successful recovery)
- Vault recovery key: 24-word BIP39 mnemonic encoding full 256-bit master key
- Enables complete offline vault recovery without server dependency (no vault salt needed)
- Display recovery keys once with secure offline storage guidance

## API Endpoints

**Authentication & Vaults:**
- `POST /v1/auth/login` - Authenticate with account password
- `POST /v1/auth/refresh` - Refresh credentials
- `POST /v1/auth/recover` - Account recovery with recovery code
- `POST /v1/vaults` - Create vault with vault salt
- `GET /v1/vaults/{id}/salt` - Retrieve vault salt for key derivation

**Item Operations (Generic for all types: MEDIA, NOTE, TASK, EVENT):**
- `POST /v1/items` - Create item (NOTE, TASK, EVENT with inline content)
- `POST /v1/items/upload/init` - Initialize upload for MEDIA items, get presigned URL
- `POST /v1/items/upload/complete` - Mark MEDIA upload complete, store metadata
- `GET /v1/items` - List items (filter by type, tags, date buckets)
- `GET /v1/items/{id}` - Get item metadata
- `PUT /v1/items/{id}` - Update item
- `DELETE /v1/items/{id}` - Delete item (MEDIA: deletes S3 + DynamoDB; NOTE/TASK/EVENT: deletes DynamoDB only)
- `GET /v1/items/{id}/download` - Get presigned download URL (for MEDIA items)

**Collections:**
- `POST /v1/collections` - Create collection
- `GET /v1/collections` - List collections
- `GET /v1/collections/{id}` - Get collection details
- `PUT /v1/collections/{id}` - Update collection
- `DELETE /v1/collections/{id}` - Delete collection
- `POST /v1/collections/{id}/items` - Add item to collection
- `DELETE /v1/collections/{id}/items/{itemId}` - Remove item from collection

**Tags & Sharing:**
- `GET /v1/tags/search` - Search by encrypted tag
- `POST /v1/shares` - Create item share
- `GET /v1/shares/{id}` - Access shared item (anonymous)
- `DELETE /v1/shares/{id}` - Revoke share

**Recovery:**
- `POST /v1/recovery/codes` - Generate account recovery codes
- `POST /v1/recovery/validate` - Validate recovery code

**Usage & Monitoring:**
- `GET /v1/usage` - Get current user's usage statistics
- `GET /v1/usage/history` - Get usage history by period
- `GET /v1/health` - Service health check (public, no auth required)

**Feature Flags (Internal):**
- Feature flags checked server-side before operations
- No dedicated API endpoints - flags control feature availability

## Operational Implementation Patterns

**Usage Tracking Pattern:**
```python
# Track usage after billable operations
from shared.usage import track_usage, UsageEventType

# After file upload
track_usage(user_id, UsageEventType.FILE_UPLOADED, {
    'file_size': size_bytes,
    'vault_id': vault_id
})

# After API call (automatic via decorator)
@track_api_call
def list_items():
    pass
```

**Quota Enforcement Pattern:**
```python
from shared.quota import check_quota, QuotaType, QuotaExceededError

try:
    # Check before expensive operation
    check_quota(user_id, QuotaType.STORAGE, additional_bytes)
    
    # Proceed with operation
    upload_file(...)
    
except QuotaExceededError as e:
    return {
        'statusCode': 429,
        'body': {
            'error': {
                'code': 'QUOTA_EXCEEDED',
                'message': str(e),
                'quota_type': e.quota_type,
                'current_usage': e.current_usage,
                'limit': e.limit
            }
        }
    }
```

**Feature Flag Pattern:**
```python
from shared.features import is_feature_enabled, FeatureFlag

# Check feature flag before operation
if not is_feature_enabled(user_id, FeatureFlag.COLLECTIONS):
    return {
        'statusCode': 403,
        'body': {'error': 'Feature not available'}
    }

# Proceed with feature
create_collection(...)
```

**Health Check Pattern:**
```python
@app.get("/v1/health")
def health_check():
    """
    Public health check endpoint (no authentication required).
    Returns service status and dependency health.
    """
    health_status = {
        'status': 'healthy',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat(),
        'dependencies': {
            'dynamodb': check_dynamodb_health(),
            's3': check_s3_health(),
            'cognito': check_cognito_health()
        }
    }
    
    # Return 503 if any critical dependency is unhealthy
    if any(not dep['healthy'] for dep in health_status['dependencies'].values()):
        return {'statusCode': 503, 'body': health_status}
    
    return {'statusCode': 200, 'body': health_status}
```

**Money Handling (Future Billing):**
```python
# Always use integers for money (cents, not dollars)
def calculate_storage_cost(bytes_used: int) -> int:
    """Calculate storage cost in cents."""
    gb_used = bytes_used / (1024 ** 3)
    cost_per_gb_cents = 10  # $0.10 per GB
    return int(gb_used * cost_per_gb_cents)

# Display to user
def format_price(cents: int) -> str:
    """Format cents as dollar string."""
    return f"${cents / 100:.2f}"
```

**TOCTOU Race Condition Protection:**
```python
# Prevent Time-of-Check-Time-of-Use vulnerabilities using conditional updates
# Example: Upload completion with S3 verification

# 1. Verify S3 object exists and get metadata
s3_metadata = self.s3_repo.get_object_metadata(s3_key)
if not s3_metadata:
    raise StorageError("Upload verification failed - object not found")

# 2. Use conditional update to prevent race conditions
try:
    self.items_repo.update_item_conditional(
        key=key,
        update_expression="SET upload_status = :status, updated_at = :updated_at REMOVE #ttl",
        condition_expression="upload_status = :pending",  # Ensures state hasn't changed
        expression_attribute_values={
            ":status": "COMPLETE",
            ":updated_at": int(now.timestamp()),
            ":pending": "PENDING",
        },
        expression_attribute_names={"#ttl": "ttl"},
    )
except StorageError:
    # Conditional update failed - verify S3 object still exists
    if not self.s3_repo.object_exists(s3_key):
        logger.error("TOCTOU race condition detected - S3 object deleted during completion")
        # Clean up orphaned metadata
        self.items_repo.delete_item(key)
        raise StorageError("Upload verification failed - object was deleted during completion")
    raise

# 3. Store S3 version ID for versioned buckets (optional but recommended)
if s3_metadata.get("version_id"):
    # Version ID provides stronger referential integrity
    update_expression += ", s3_version_id = :version_id"
    expression_attribute_values[":version_id"] = s3_metadata["version_id"]
```

**Key Points:**
- Use DynamoDB conditional expressions to prevent concurrent modifications
- Verify external resources (S3) before and after critical operations
- Store version IDs when available for stronger referential integrity
- Detect race conditions by re-checking resource existence on conditional update failure
- Clean up orphaned metadata when race conditions are detected
- Prevents OWASP A04:2021 - Insecure Design vulnerabilities

**Item Deletion Pattern (Atomic Multi-Resource Cleanup):**
```python
# Deletion pattern for MEDIA items (S3 + DynamoDB)
# 1. Verify user ownership
# 2. Handle pending uploads (abort multipart if needed)
# 3. Delete S3 object first
# 4. Delete DynamoDB metadata
# 5. Log orphaned S3 objects if DynamoDB deletion fails

def delete_media_item(user_id, vault_id, item_id, item, item_key):
    s3_key = item.get("s3_key")
    
    # Handle pending uploads
    if item.get("upload_status") == "PENDING":
        if upload_id := item.get("upload_id"):
            self.s3_repo.abort_multipart_upload(s3_key, upload_id)
        self.items_repo.delete_item(item_key)
        return
    
    # Delete S3 object first
    try:
        self.s3_repo.delete_object(s3_key)
    except StorageError:
        raise StorageError("Failed to delete media file")
    
    # Delete DynamoDB metadata
    try:
        self.items_repo.delete_item(item_key)
    except StorageError:
        # Log orphaned S3 object for manual cleanup
        logger.warning(
            "DynamoDB deletion failed after S3 deletion - orphaned S3 object",
            extra={"s3_key": s3_key, "action": "manual_cleanup_required"}
        )
        raise StorageError("Failed to delete item metadata - S3 object deleted but metadata remains")

# For NOTE/TASK/EVENT items: Delete DynamoDB only (no S3 object)
def delete_inline_item(user_id, vault_id, item_id, item_key):
    self.items_repo.delete_item(item_key)
```

**Key Points:**
- Delete S3 object before DynamoDB metadata (fail fast if S3 fails)
- Handle pending uploads by aborting multipart uploads
- Log orphaned S3 objects when DynamoDB deletion fails (enables manual cleanup)
- Different deletion paths for MEDIA vs inline items (NOTE/TASK/EVENT)
- Verify user ownership before any deletion operations
- Comprehensive error handling and logging for debugging

## Testing Requirements

**Property-Based Testing**
- Use Hypothesis (Python) for server-side property tests
- Use fast-check (TypeScript/JavaScript) for React frontend property tests
- Minimum 100 iterations per property test
- Each property test must reference design document property in comment
- Tag format: `# Feature: cortex-backup, Property {number}: {property_text}`
- Test data generators for: media content, metadata, users, tags, collections, passwords
- Property tests verify universal correctness across many random inputs

**Property Test Examples:**
- Encryption round-trip preserves content
- User data isolation (vault boundaries)
- Pagination consistency (no duplicates, no omissions)
- Deletion maintains referential integrity
- Key derivation is deterministic
- Encrypted tag search functionality
- Password strength validation
- Breached password detection
- Account recovery code validation

**Unit & Integration Tests:**
- Write unit tests for all Lambda functions
- **CRITICAL: Use botocore Stubber for AWS service testing - DO NOT use mocking libraries (unittest.mock, MagicMock, etc.)**
- botocore Stubber provides type-safe, realistic AWS API responses without actual AWS calls
- Stubber validates request parameters and response structures match actual AWS APIs
- Aim for >80% code coverage
- Test error paths and edge cases

**botocore Stubber Pattern:**
```python
import boto3
from botocore.stub import Stubber
from unittest.mock import ANY  # Use for dynamic/generated values

# Create real boto3 resource
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('test-table')

# Create stubber for the underlying client
stubber = Stubber(table.meta.client)

# Add expected response - use ANY for parameters that boto3 transforms
stubber.add_response(
    'put_item',
    {},  # Response
    {
        'TableName': 'test-table',
        'Item': ANY,  # Use ANY when boto3 transforms high-level to low-level format
        'ConditionExpression': ANY,
    }
)

# Activate stubber
with stubber:
    # Call service method
    result = service.create_vault(user_id='123')
    
# Stubber automatically validates all expected calls were made
stubber.assert_no_pending_responses()
```

**Using Stubber Fixtures (Recommended):**
```python
# Test fixtures provide pre-configured stubbers (see lambda/tests/fixtures/boto.py)
def test_s3_operation(s3_stubber, s3_bucket_name, s3_client):
    """Test using fixture-provided stubber."""
    # Create repository and inject stubbed client
    repo = S3Repository(bucket_name=s3_bucket_name)
    repo.s3_client = s3_client
    
    # Configure stubber response
    s3_stubber.add_response(
        'head_object',
        {'ContentLength': 100, 'ContentType': 'image/jpeg'},
        {'Bucket': s3_bucket_name, 'Key': 'test-key'}
    )
    
    # Call method - stubber validates automatically
    result = repo.object_exists('test-key')
    assert result is True
```

**Why botocore Stubber over mocking:**
- Type safety: Validates request/response structures match AWS APIs
- Realistic testing: Uses actual boto3 client code paths
- Catches API misuse: Fails if parameters don't match AWS API expectations
- No mock drift: Stubber stays in sync with boto3 library updates
- Better refactoring: Changes to AWS calls are caught by tests
- Use `unittest.mock.ANY` for dynamic values (generated IDs, timestamps, etc.)

## Kiro Specs

Specs are a structured way of building and documenting features with Kiro. They formalize the design and implementation process, allowing iteration on requirements and design before implementation.

**What are Specs?**
- Structured feature development workflow with distinct phases
- Formalization of design and implementation process
- Enable incremental development of complex features with control and feedback
- Allow iteration with the agent on requirements, design, and implementation tasks

**File References in Specs**
- Specs support file references via `#[[file:<relative_file_name>]]` syntax
- Include references to OpenAPI specs, GraphQL schemas, or design documents
- Referenced files influence implementation in a low-friction way
- Example: `#[[file:api/openapi.yaml]]` or `#[[file:docs/design.md]]`

**When to Use Specs**
- Complex features requiring design iteration before implementation
- Features spanning multiple files or components
- When you need to document requirements and design decisions
- API changes or new endpoint development
- Encryption algorithm changes or security feature additions
- Major refactoring efforts

**Spec Workflow**
1. Define requirements and acceptance criteria
2. Iterate on design with Kiro
3. Break down into implementation tasks
4. Let Kiro work through implementation incrementally
5. Review and provide feedback at each stage

**Best Practices for This Project**
- Use specs for new API endpoints (reference Smithy models)
- Use specs for encryption changes (reference security requirements)
- Use specs for new Lambda routes (reference API Gateway integration)
- Include references to relevant DynamoDB schema patterns
- Reference property-based testing requirements in implementation tasks
