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

## Architecture Patterns

**Zero-Knowledge Design**
- All encryption/decryption MUST happen client-side
- Server never has access to encryption keys or unencrypted data
- Metadata, tags, and collections are encrypted before storage
- Two-password model: account password (Cognito) vs vault password (key derivation)
- Vault password never transmitted to server
- Vault salt stored on server (non-secret, enables multi-device key derivation)
- Share keys embedded in URL fragments (never sent to server)

**Performance-First Approach**
- Use presigned S3 URLs for direct client-to-S3 uploads/downloads (bypass Lambda)
- Implement S3 multipart upload for files >5MB (minimum part size, up to 10,000 parts)
- Enable S3 Transfer Acceleration for global users
- Concurrent uploads with configurable limits
- Use DynamoDB pagination for large result sets
- Create appropriate DynamoDB GSIs for query optimization

**Serverless Best Practices**
- Lambda functions should be stateless
- Use Lambda layers for shared dependencies
- Implement proper error handling and retries
- Use dead letter queues for failed invocations
- Set appropriate Lambda timeout and memory (optimize for cost/performance)

**Key Rotation Pattern**
- Automatic rotation every 90 days
- Generate new derived keys from vault master key (updated HKDF context)
- Background re-encryption in batches
- Dual-key access during transition (old keys for reading, new keys for writing)
- Update metadata with key version

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

Example Lambda handler structure:
```python
# handler.py - Main entry point
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from routes import auth, vaults, media, collections, tags, shares, recovery

logger = Logger()
tracer = Tracer()
metrics = Metrics()
app = APIGatewayRestResolver()

# Register all route modules
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

```python
# routes/media.py - Route handlers for media operations
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from services.media_service import MediaService
from shared.auth import get_user_from_context

logger = Logger(child=True)
tracer = Tracer()

def register_routes(app: APIGatewayRestResolver):
    @app.post("/v1/media/upload/init")
    @tracer.capture_method
    def init_upload():
        user_id = get_user_from_context(app.current_event)
        body = app.current_event.json_body
        
        service = MediaService()
        response = service.initiate_upload(user_id, body)
        return response
    
    @app.get("/v1/media/list")
    @tracer.capture_method
    def list_media():
        user_id = get_user_from_context(app.current_event)
        params = app.current_event.query_string_parameters or {}
        
        service = MediaService()
        response = service.list_media(user_id, params)
        return response
    
    @app.get("/v1/media/<media_id>")
    @tracer.capture_method
    def get_media(media_id: str):
        user_id = get_user_from_context(app.current_event)
        
        service = MediaService()
        response = service.get_media(user_id, media_id)
        return response
    
    @app.delete("/v1/media/<media_id>")
    @tracer.capture_method
    def delete_media(media_id: str):
        user_id = get_user_from_context(app.current_event)
        
        service = MediaService()
        service.delete_media(user_id, media_id)
        return {"message": "Media deleted successfully"}
```

```python
# services/media_service.py - Business logic
from aws_lambda_powertools import Logger, Tracer
from shared.repository import MediaRepository, S3Repository

logger = Logger(child=True)
tracer = Tracer()

class MediaService:
    def __init__(self):
        self.media_repo = MediaRepository()
        self.s3_repo = S3Repository()
    
    @tracer.capture_method
    def initiate_upload(self, user_id: str, request: dict) -> dict:
        # Business logic here
        presigned_url = self.s3_repo.generate_upload_url(user_id, request)
        return {"upload_url": presigned_url, "expires_in": 900}
    
    @tracer.capture_method
    def list_media(self, user_id: str, params: dict) -> dict:
        # Business logic here
        items = self.media_repo.list_by_user(user_id, params)
        return {"items": items}
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

## Deployment Considerations

- Use CDK deployment stages (dev, staging, prod)
- Single Lambda function deployment with versioning and aliases
- Implement gradual Lambda deployments with aliases (canary or linear)
- Use CloudWatch alarms for monitoring (error rates, throttling, latency)
- Set up X-Ray tracing for distributed debugging
- Configure appropriate Lambda reserved concurrency
- Implement proper backup and disaster recovery strategies
- Blue-green deployment for zero-downtime updates
- DynamoDB point-in-time recovery enabled
- S3 versioning enabled for accidental deletion protection

**Single Lambda Deployment Strategy:**
- Package all route handlers and dependencies together
- Use Lambda layers for large dependencies (if needed)
- Set appropriate timeout (30s recommended for API operations)
- Set appropriate memory (512MB-1024MB recommended)
- Enable Lambda function URL or use API Gateway proxy integration
- Monitor cold start metrics and optimize package size
- Use provisioned concurrency for production if needed

**Cost Optimization:**
- S3 lifecycle policies: transition to Glacier after 90 days of no access
- S3 Intelligent-Tiering for automatic cost optimization
- Delete incomplete multipart uploads after 7 days
- DynamoDB on-demand billing or provisioned with auto-scaling
- Lambda ARM-based Graviton2 for 20% cost savings
- Optimize Lambda memory allocation for cost/performance balance

**Monitoring:**
- CloudWatch metrics: Lambda invocations, API Gateway requests, DynamoDB capacity, S3 operations
- CloudWatch alarms: Lambda error rate >1%, API Gateway 5xx >0.5%, DynamoDB throttling
- X-Ray tracing for end-to-end request analysis
- Log retention policies for compliance

## API Endpoints

**Authentication & Vaults:**
- `POST /v1/auth/login` - Authenticate with account password
- `POST /v1/auth/refresh` - Refresh credentials
- `POST /v1/auth/recover` - Account recovery with recovery code
- `POST /v1/vaults` - Create vault with vault salt
- `GET /v1/vaults/{id}/salt` - Retrieve vault salt for key derivation

**Media Operations:**
- `POST /v1/media/upload/init` - Initialize upload, get presigned URL
- `POST /v1/media/upload/complete` - Mark upload complete, store metadata
- `GET /v1/media/list` - List user's media (paginated)
- `GET /v1/media/{id}` - Get media metadata
- `GET /v1/media/{id}/download` - Get presigned download URL
- `DELETE /v1/media/{id}` - Delete media item

**Collections:**
- `POST /v1/collections` - Create collection
- `GET /v1/collections` - List collections
- `GET /v1/collections/{id}` - Get collection details
- `PUT /v1/collections/{id}` - Update collection
- `DELETE /v1/collections/{id}` - Delete collection
- `POST /v1/collections/{id}/media` - Add media to collection
- `DELETE /v1/collections/{id}/media/{mediaId}` - Remove media from collection

**Tags & Sharing:**
- `GET /v1/tags/search` - Search by encrypted tag
- `POST /v1/shares` - Create file share
- `GET /v1/shares/{id}` - Access shared file (anonymous)
- `DELETE /v1/shares/{id}` - Revoke share

**Recovery:**
- `POST /v1/recovery/codes` - Generate account recovery codes
- `POST /v1/recovery/validate` - Validate recovery code

## Smithy Model

**Service Definition:**
- Namespace: `com.cortex.backup`
- Version: `2024-01-01`
- All operations, inputs, outputs, and errors defined in Smithy
- Automatic generation of: OpenAPI 3.0 spec, client SDKs, server stubs, API documentation

**Error Response Format:**
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "requestId": "unique-request-id",
    "timestamp": "2024-01-01T00:00:00Z"
  }
}
```

**Error Codes:**
- `AUTHENTICATION_REQUIRED` - User must authenticate (401)
- `AUTHENTICATION_FAILED` - Invalid credentials (401)
- `AUTHORIZATION_FAILED` - User lacks permission (403)
- `RESOURCE_NOT_FOUND` - Requested resource doesn't exist (404)
- `INVALID_REQUEST` - Malformed request (400)
- `RATE_LIMIT_EXCEEDED` - Too many requests (429)
- `INTERNAL_ERROR` - Server-side error (500)
- `STORAGE_ERROR` - S3 or DynamoDB error (500)
- `SHARE_EXPIRED` - Share link has expired (403)
- `SHARE_REVOKED` - Share has been revoked (403)
- `RECOVERY_CODE_INVALID` - Recovery code invalid or used (401)
- `PASSWORD_TOO_WEAK` - Password doesn't meet requirements (400)
- `PASSWORD_BREACHED` - Password found in breach database (400)
- `VAULT_SALT_NOT_FOUND` - Vault salt not found (404)

## Client-Side Libraries

**Encryption (@noble/ciphers):**
```typescript
import { chacha20poly1305 } from '@noble/ciphers/chacha';

function encryptData(plaintext: Uint8Array, key: Uint8Array): Uint8Array {
  const nonce = randomBytes(12); // 96-bit nonce
  const cipher = chacha20poly1305(key, nonce);
  const ciphertext = cipher.encrypt(plaintext);
  return concat(nonce, ciphertext); // nonce + ciphertext + tag
}
```

**Key Derivation (argon2-browser):**
```typescript
import argon2 from 'argon2-browser';

async function deriveVaultMasterKey(
  vaultPassword: string,
  vaultSalt: Uint8Array
): Promise<Uint8Array> {
  const result = await argon2.hash({
    pass: vaultPassword,
    salt: vaultSalt,
    type: argon2.ArgonType.Argon2id,
    mem: 65536, // 64MB
    time: 3,    // 3 iterations
    parallelism: 4,
    hashLen: 32 // 256-bit output
  });
  return result.hash;
}
```

**HKDF (@noble/hashes):**
```typescript
import { hkdf } from '@noble/hashes/hkdf';
import { sha256 } from '@noble/hashes/sha256';

function deriveKeys(vaultMasterKey: Uint8Array) {
  const dataKey = hkdf(sha256, vaultMasterKey, undefined, 
    'cortex-data-encryption-v1', 32);
  const metadataKey = hkdf(sha256, vaultMasterKey, undefined, 
    'cortex-metadata-encryption-v1', 32);
  const shareKey = hkdf(sha256, vaultMasterKey, undefined, 
    'cortex-share-key-derivation-v1', 32);
  return { dataKey, metadataKey, shareKey };
}
```

**Password Validation:**
```typescript
import { sha1 } from '@noble/hashes/sha1';

async function checkPasswordBreach(password: string): Promise<boolean> {
  const hash = sha1(password).toString('hex').toUpperCase();
  const prefix = hash.substring(0, 5);
  const suffix = hash.substring(5);
  
  const response = await fetch(
    `https://api.pwnedpasswords.com/range/${prefix}`
  );
  const hashes = await response.text();
  
  return hashes.includes(suffix);
}
```
