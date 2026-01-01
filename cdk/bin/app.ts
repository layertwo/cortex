#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { StorageStack } from '../lib/storage-stack';
import { DatabaseStack } from '../lib/database-stack';
import { AuthStack } from '../lib/auth-stack';
import { ApiStack } from '../lib/api-stack';

const app = new cdk.App();

// Get environment from context or default to 'dev'
const env = app.node.tryGetContext('env') || 'dev';
const envConfig = app.node.tryGetContext('cortex')?.[env];

if (!envConfig) {
  throw new Error(`Environment configuration not found for: ${env}`);
}

const stackEnv = {
  account: envConfig.account || process.env.CDK_DEFAULT_ACCOUNT,
  region: envConfig.region || process.env.CDK_DEFAULT_REGION,
};

// Stack naming convention: cortex-{env}-{resource-type}
const stackPrefix = `cortex-${env}`;

// Storage Stack - S3 bucket for encrypted files
const storageStack = new StorageStack(app, `${stackPrefix}-storage`, {
  env: stackEnv,
  description: 'Cortex storage infrastructure (S3)',
  stackName: `${stackPrefix}-storage`,
});

// Database Stack - DynamoDB tables
const databaseStack = new DatabaseStack(app, `${stackPrefix}-database`, {
  env: stackEnv,
  description: 'Cortex database infrastructure (DynamoDB)',
  stackName: `${stackPrefix}-database`,
});

// Auth Stack - Cognito user pool and identity pool
const authStack = new AuthStack(app, `${stackPrefix}-auth`, {
  env: stackEnv,
  description: 'Cortex authentication infrastructure (Cognito)',
  stackName: `${stackPrefix}-auth`,
});

// API Stack - Lambda function and API Gateway
const apiStack = new ApiStack(app, `${stackPrefix}-api`, {
  env: stackEnv,
  description: 'Cortex API infrastructure (Lambda + API Gateway)',
  stackName: `${stackPrefix}-api`,
  bucket: storageStack.bucket,
  usersTable: databaseStack.usersTable,
  vaultsTable: databaseStack.vaultsTable,
  filesTable: databaseStack.filesTable,
  collectionsTable: databaseStack.collectionsTable,
  fileCollectionAssociationsTable: databaseStack.fileCollectionAssociationsTable,
  sharesTable: databaseStack.sharesTable,
  accountRecoveryTable: databaseStack.accountRecoveryTable,
  userPool: authStack.userPool,
  userPoolClient: authStack.userPoolClient,
});

// Add tags to all stacks
cdk.Tags.of(app).add('Project', 'Cortex');
cdk.Tags.of(app).add('Environment', env);
cdk.Tags.of(app).add('ManagedBy', 'CDK');
