# Cortex Backup System

A zero-knowledge cloud file storage and backup solution with client-side encryption.

## Overview

Cortex is a privacy-first backup system where all encryption happens client-side. The backend never has access to unencrypted user data, metadata, or encryption keys.

### Key Features

- **Zero-Knowledge Architecture**: Server never sees plaintext data or encryption keys
- **Client-Side Encryption**: ChaCha20-Poly1305 encryption on all user devices
- **Two-Password Model**: Separate account password (authentication) and vault password (encryption)
- **Multi-Device Support**: Access encrypted data from any device using vault password
- **Encrypted Search**: Tag-based organization with deterministic encryption
- **Secure Sharing**: Share files with unique share keys and optional password protection
- **Automatic Key Rotation**: Keys rotate every 90 days with background re-encryption

## Project Structure

```
cortex/
├── infrastructure/         # CDK stacks (TypeScript)
│   ├── lib/               # Stack definitions
│   └── bin/app.ts         # CDK entry point
├── api/smithy/            # Smithy API models
├── lambda/                # Python Lambda handlers
│   ├── api/              # Main API handler
│   └── shared/           # Common utilities
├── client/                # Client-side encryption library
│   └── src/              # TypeScript source
└── tests/                 # Test suites
    ├── unit/
    ├── integration/
    └── property/
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- AWS CLI configured
- AWS CDK CLI (`npm install -g aws-cdk`)

### Infrastructure Setup

```bash
cd infrastructure
npm install
npm run build
cdk synth
cdk deploy --all
```

### Lambda Development

```bash
cd lambda
pip install -r requirements.txt
pytest
```

### Client Library

```bash
cd client
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

1. **Account Password**: Authenticates with AWS Cognito
2. **Vault Password**: Derives encryption keys (never transmitted to server)
3. **Vault Salt**: Stored on server (non-secret), enables multi-device key derivation
4. **Vault Master Key**: Derived from vault password + salt using Argon2id
5. **Derived Keys**: Data encryption key, metadata encryption key, share key derivation key

## Development

### CDK Commands

- `npm run build` - Compile TypeScript
- `cdk synth` - Generate CloudFormation templates
- `cdk diff` - Preview infrastructure changes
- `cdk deploy` - Deploy stacks to AWS

### Testing

- Unit tests: `pytest tests/unit/`
- Integration tests: `pytest tests/integration/`
- Property-based tests: `pytest tests/property/`

## License

ISC
