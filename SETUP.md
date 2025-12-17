# Cortex Backup System - Setup Guide

This guide will help you set up the development environment for the Cortex Backup System.

## Prerequisites

- **Node.js**: 18+ and npm
- **Python**: 3.11+
- **AWS CLI**: Configured with appropriate credentials
- **AWS CDK CLI**: Install globally with `npm install -g aws-cdk`

## Project Structure

The project is organized into the following main directories:

- `infrastructure/` - AWS CDK infrastructure code (TypeScript)
- `lambda/` - Python Lambda functions for the API
- `client/` - Client-side encryption library (TypeScript)
- `api/smithy/` - Smithy API model definitions
- `tests/` - Test suites (unit, integration, property-based)

## Initial Setup

### 1. Infrastructure (CDK)

```bash
cd infrastructure
npm install
npm run build
```

To synthesize CloudFormation templates:
```bash
npm run synth
```

To preview changes:
```bash
npm run diff
```

To deploy (when ready):
```bash
cdk deploy --all
```

### 2. Lambda Functions

```bash
cd lambda
pip install -r requirements.txt
```

To run tests:
```bash
cd ..
pytest tests/unit/
```

### 3. Client Library

```bash
cd client
npm install
npm run build
```

To run tests:
```bash
npm test
```

## Environment Configuration

### CDK Context

The CDK configuration in `infrastructure/cdk.json` includes environment-specific settings:

- `dev` - Development environment
- `staging` - Staging environment
- `prod` - Production environment

Update the account IDs and regions in `cdk.json` before deploying.

### Lambda Environment Variables

Lambda functions will receive the following environment variables (configured by CDK):

- `USERS_TABLE` - DynamoDB Users table name
- `VAULTS_TABLE` - DynamoDB Vaults table name
- `FILES_TABLE` - DynamoDB Files table name
- `COLLECTIONS_TABLE` - DynamoDB Collections table name
- `FILE_COLLECTION_ASSOCIATIONS_TABLE` - DynamoDB File-Collection associations table name
- `SHARES_TABLE` - DynamoDB Shares table name
- `ACCOUNT_RECOVERY_TABLE` - DynamoDB Account Recovery table name
- `FILES_BUCKET` - S3 bucket name for encrypted files

## Development Workflow

### Making Changes

1. **Infrastructure changes**: Edit files in `infrastructure/lib/`
2. **Lambda code**: Edit files in `lambda/api/` or `lambda/shared/`
3. **Client library**: Edit files in `client/src/`

### Testing

Run tests before committing:

```bash
# Python tests
pytest

# Client tests
cd client && npm test
```

### Building

```bash
# Build infrastructure
cd infrastructure && npm run build

# Build client library
cd client && npm run build
```

## Next Steps

The project structure is now set up. The next tasks will implement:

1. Smithy API model definitions
2. CDK stacks for AWS resources (S3, DynamoDB, Cognito, Lambda, API Gateway)
3. Lambda function handlers and business logic
4. Client-side encryption library
5. Comprehensive test suites

Refer to `.kiro/specs/cortex-backup/tasks.md` for the complete implementation plan.

## Troubleshooting

### CDK Bootstrap

If you haven't used CDK in your AWS account before, you'll need to bootstrap it:

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### Python Dependencies

If you encounter issues with Python dependencies, ensure you're using Python 3.11+:

```bash
python --version
```

Consider using a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r lambda/requirements.txt
```

### Node Dependencies

If npm install fails, try clearing the cache:

```bash
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

## Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Lambda Powertools Python](https://docs.powertools.aws.dev/lambda/python/)
- [Smithy Documentation](https://smithy.io/)
- [Design Document](.kiro/specs/cortex-backup/design.md)
- [Requirements Document](.kiro/specs/cortex-backup/requirements.md)
