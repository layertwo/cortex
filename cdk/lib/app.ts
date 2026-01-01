#!/usr/bin/env node
import {App, Environment} from "aws-cdk-lib";

import {STAGES} from "./config";
import {ApiStack} from "./stacks/api-stack";
import {AuthStack} from "./stacks/auth-stack";
import {DatabaseStack} from "./stacks/database-stack";
import {StorageStack} from "./stacks/storage-stack";

const app = new App();

STAGES.forEach((stage) => {
    const env: Environment = {
        account: stage.account,
        region: stage.region,
    };

    // Stack naming convention: cortex-{env}-{resource-type}
    const stackPrefix = `cortex-${stage.stageType.toLowerCase()}`;

    // Storage Stack - S3 bucket for encrypted files
    const storageStack = new StorageStack(app, `${stackPrefix}-storage`, {
        env,
        description: "Cortex storage infrastructure (S3)",
        stackName: `${stackPrefix}-storage`,
    });

    // Database Stack - DynamoDB tables
    const databaseStack = new DatabaseStack(app, `${stackPrefix}-database`, {
        env,
        description: "Cortex database infrastructure (DynamoDB)",
        stackName: `${stackPrefix}-database`,
    });

    // Auth Stack - Cognito user pool and identity pool
    const authStack = new AuthStack(app, `${stackPrefix}-auth`, {
        env,
        description: "Cortex authentication infrastructure (Cognito)",
        stackName: `${stackPrefix}-auth`,
    });

    // API Stack - Lambda function and API Gateway
    new ApiStack(app, `${stackPrefix}-api`, {
        env,
        description: "Cortex API infrastructure",
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
});

app.synth();
