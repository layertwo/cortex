# Cortex Backup System

A zero-knowledge cloud file storage and backup solution with client-side encryption.

## Overview

Cortex is a privacy-first backup system where all encryption happens client-side. The backend never has access to unencrypted user data, metadata, or encryption keys.

### Key Features

- **Zero-Knowledge Architecture**: Server never sees plaintext data or encryption keys
- **Client-Side Encryption**: ChaCha20-Poly1305 encryption on all user devices
- **Two-Password Model**: Separate account password (authentication) and vault password (encryption)
- **Account Recovery**: Cognito-hosted email forgot-password for the account password; separate 24-word BIP39 mnemonic for vault recovery
- **Multi-Device Support**: Access encrypted data from any device using vault password
- **Collections**: Organize items into collections with many-to-many relationships
- **Encrypted Search**: Tag-based organization with deterministic encryption
- **Secure Sharing**: Share files with unique share keys and optional password protection
- **Automatic Key Rotation**: Keys rotate every 90 days with background re-encryption

## Project Structure

```
cortex/
├── cdk/                   # CDK stacks (TypeScript)
│   ├── lib/               # Stack definitions
│   │   ├── stacks/        # auth.ts, service.ts
│   │   ├── app.ts         # CDK entry point
│   │   └── config.ts      # Environment configuration
│   └── cdk.json
├── smithy/                # Smithy API models
│   └── models/            # vault/, item/, collection/, tag/, share/
├── lambda/                # Python Lambda handlers
│   ├── src/
│   │   ├── api/           # Routes and services
│   │   │   ├── routes/    # vaults, items, collections, tags, shares
│   │   │   └── services/  # Business logic layer
│   │   ├── entrypoint/    # Lambda entry point (api.py)
│   │   ├── environment/   # Service provider
│   │   └── shared/        # Common utilities (auth, models, repository, util)
│   └── tests/             # Unit, integration, and property tests
├── packages/              # Monorepo packages (npm workspaces)
│   ├── encryption/        # @cortex/encryption - Standalone encryption library
│   │   ├── src/lib/       # encryption, envelope-encryption, key-management, key-storage, password-validation
│   │   └── tests/         # Unit and property tests
│   └── web/               # @cortex/web - React web application
│       └── src/           # App.tsx, main.tsx
└── package.json           # Root workspace configuration
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- AWS CLI configured
- AWS CDK CLI (`npm install -g aws-cdk`)

### Infrastructure Setup

```bash
cd cdk
npm install
npm run build
cdk synth
cdk deploy --all
```

### Lambda Development

```bash
cd lambda
uv sync
uv run pytest
```

### Encryption Library

```bash
cd packages/encryption
npm install
npm run build
npm test
```

## Architecture

### Technology Stack

- **Infrastructure**: AWS CDK with TypeScript
- **Backend**: AWS Lambda (Python 3.11+) with Lambda Powertools
- **API**: AWS API Gateway + Smithy models
- **Storage**: AWS S3 (encrypted files) + DynamoDB (encrypted metadata)
- **Authentication**: AWS Cognito
- **Client Encryption**: ChaCha20-Poly1305 via @noble/ciphers
- **Key Derivation**: Argon2id + HKDF

### Security Model

1. **Account Password**: Authenticates with AWS Cognito via Amplify (SRP) directly from the browser; the account password is never transmitted to the Cortex backend
2. **Account Recovery**: Cognito-hosted forgot-password (email-based) resets the account password; no recovery codes are stored by Cortex
3. **Vault Password**: Derives encryption keys (never transmitted to server)
4. **Vault Salt**: Stored on server (non-secret), enables multi-device key derivation
5. **Vault Master Key**: Derived from vault password + salt using Argon2id
6. **Derived Keys**: KEK (Key Encryption Key), metadata encryption key, share key derivation key
7. **Envelope Encryption**: Each media file encrypted with a unique DEK, DEK wrapped with KEK

**Recovery Options:**
- **Account Recovery**: Cognito forgot-password flow (email verification) resets the account password; the account password and recovery flow are handled entirely by Cognito and never reach the Cortex backend
- **Vault Recovery**: 24-word BIP39 mnemonic enables vault password reset without re-encrypting data

## Implementation Status

### ✅ Completed Features

- **Infrastructure**: CDK stacks for S3, DynamoDB, Cognito, API Gateway, Lambda
- **Authentication**: Account authentication via AWS Cognito (Amplify frontend-direct SRP; API Gateway Cognito authorizer validates JWTs), vault salt management
- **Item Management**: Create, upload, list, retrieve, update, delete items (MEDIA, NOTE, TASK, EVENT types)
- **Collection Management**: Create, list, retrieve, update, delete collections with many-to-many item associations
- **Tag Search**: Search items by encrypted tags with vault isolation and pagination
- **Encryption Library**: ChaCha20-Poly1305 encryption, envelope encryption (DEK/KEK), Argon2id key derivation, password validation
- **API Layer**: Single Lambda function with APIGatewayRestResolver handling all routes
- **Testing**: Unit tests with botocore Stubber, property-based tests with Hypothesis
- **File Sharing**: Create/access/revoke shares with envelope encryption, server-side rate limiting, and anonymous presigned-URL downloads

### 🚧 In Progress

- React web application
- Automatic key rotation

## Development

### CDK Commands

```bash
cd cdk
npm run build      # Compile TypeScript
cdk synth          # Generate CloudFormation templates
cdk diff           # Preview infrastructure changes
cdk deploy         # Deploy stacks to AWS
```

### Testing

```bash
cd lambda
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/property/       # Property-based tests
```

## License

MIT
