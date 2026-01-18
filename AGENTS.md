# Cortex: Zero-Knowledge Media Backup System

Cortex is a privacy-first photo and video backup solution where all encryption happens client-side. The backend never has access to unencrypted user data, metadata, or encryption keys.

## Critical Architecture Constraints

**Zero-Knowledge Enforcement:**
- Backend MUST NEVER receive or process unencrypted user data
- All encryption/decryption operations happen exclusively on client devices
- Metadata (filenames, dates, locations), tags, and collections are encrypted before transmission
- Server only stores encrypted blobs and cannot decrypt them

**Data Flow Pattern:**
- Client encrypts data → Client uploads directly to S3 via presigned URL → Server stores encrypted metadata in DynamoDB
- Client requests presigned URL → Client downloads from S3 → Client decrypts locally
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
- Vault recovery key (BIP39 mnemonic) enables vault password reset without re-encryption
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

**Client-Side Encryption**: ChaCha20-Poly1305
- Library: @noble/ciphers (browser), cryptography (Python for testing)
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

**Tag Encryption**: Deterministic HMAC-SHA256
- Enables server-side exact match without revealing plaintext
- Consistent output for same tag (searchability)
- Tags normalized to lowercase before encryption

## Directory Structure

```
cortex/
├── cdk/                   # CDK stacks (TypeScript)
│   ├── lib/               # Stack definitions
│   │   ├── storage-stack.ts
│   │   ├── database-stack.ts
│   │   ├── auth-stack.ts
│   │   └── api-stack.ts
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
│   │   └── recovery/
│   └── smithy-build.json
├── lambda/                # Python Lambda handlers
│   ├── api/              # Main API handler using Lambda Powertools
│   │   ├── handler.py    # Entry point with APIGatewayRestResolver
│   │   ├── routes/       # Route handlers organized by domain
│   │   │   ├── auth.py       # Authentication routes
│   │   │   ├── vaults.py     # Vault management routes
│   │   │   ├── items.py      # Item CRUD routes (all types: MEDIA, NOTE, TASK, EVENT)
│   │   │   ├── collections.py # Collection CRUD routes
│   │   │   ├── tags.py       # Tag search routes
│   │   │   ├── shares.py     # Item sharing routes
│   │   │   └── recovery.py   # Account recovery routes
│   │   └── services/     # Business logic layer
│   │       ├── item_service.py
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
- API models: `smithy/models/{domain}/{resource}.smithy`
- Tests: `tests/{unit|integration}/test_{module}.py`

**Naming conventions:**
- TypeScript: kebab-case files, PascalCase classes (`storage-stack.ts` → `StorageStack`)
- Python: snake_case for files and functions
- Smithy: kebab-case with namespace `com.cortex.{service}`

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

**Python Lambda (route module example - routes/items.py):**
```python
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from services.item_service import ItemService
from shared.models import CreateItemRequest, CreateItemResponse, ItemType
from shared.auth import get_user_from_context

logger = Logger(child=True)
tracer = Tracer()

def register_routes(app: APIGatewayRestResolver):
    @app.post("/v1/items")
    @tracer.capture_method
    def create_item():
        user_id = get_user_from_context(app.current_event)
        body = app.current_event.json_body
        request = CreateItemRequest(**body)
        
        service = ItemService()
        response = service.create_item(user_id, request)
        
        return response.dict()
    
    @app.get("/v1/items")
    @tracer.capture_method
    def list_items():
        user_id = get_user_from_context(app.current_event)
        params = app.current_event.query_string_parameters or {}
        item_type = params.get("itemType")  # Optional filter
        page_size = int(params.get("pageSize", 50))
        next_token = params.get("nextToken")
        
        service = ItemService()
        response = service.list_items(user_id, item_type, page_size, next_token)
        
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

## Security Requirements

- Never log sensitive data (keys, passwords, PII, encrypted payloads)
- Log only: user IDs, vault IDs, timestamps, operation types, error codes, performance metrics
- Never log: vault password, vault keys, vault recovery keys, share keys, account recovery codes
- Use AWS Secrets Manager or Parameter Store for secrets
- Implement least-privilege IAM policies for Lambda execution roles
- No per-user IAM policies (use scoped presigned URLs instead)
- Enable CloudTrail logging for audit trails
- Use VPC endpoints for private AWS service access when needed
- Validate all inputs at API Gateway and Lambda layers
- Sanitize error messages to prevent information leakage

**Password Security:**
- Minimum 12 characters
- Require: uppercase, lowercase, numbers, special characters
- Breach detection via Have I Been Pwned API (k-anonymity model)
- Client-side SHA-1 hash, send first 5 characters to API
- Check full hash against returned list locally
- Reject any password found in breach database

**Recovery Security:**
- Account recovery codes: 10 per user, 16 characters, format: XXXX-XXXX-XXXX-XXXX
- Codes hashed with SHA-256 before server storage
- One-time use (invalidated after successful recovery)
- Vault recovery key: BIP39 mnemonic (12-24 words), never stored on server
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
- `DELETE /v1/items/{id}` - Delete item
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

## Testing Requirements

**Property-Based Testing**
- Use Hypothesis (Python) for server-side property tests
- Use fast-check (TypeScript/JavaScript) for client-side property tests
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

**Unit & Integration Tests:**
- Write unit tests for all Lambda functions
- Use moto for mocking AWS services in tests
- Aim for >80% code coverage
- Test error paths and edge cases

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
