#!/usr/bin/env node
import {App, Environment} from "aws-cdk-lib";

import {STAGES} from "./config";
import {AuthStack} from "./stacks/auth";
import {ServiceStack} from "./stacks/service";

const app = new App();

STAGES.forEach((stage) => {
    const env: Environment = {
        account: stage.account,
        region: stage.region,
    };

    // Stack naming convention: cortex-{env}-{resource-type}
    const stackPrefix = `cortex-${stage.stageType.toLowerCase()}`;

    // Auth Stack - Cognito user pool and app client
    const authStack = new AuthStack(app, `${stackPrefix}-auth`, {
        env,
        stage,
        description: "Cortex authentication infrastructure (Cognito)",
        stackName: `${stackPrefix}-auth`,
    });

    // Service Stack - Storage, Database, and API
    new ServiceStack(app, `${stackPrefix}-service`, {
        env,
        stage,
        userPool: authStack.userPool,
        userPoolClient: authStack.userPoolClient,
        description: "Cortex service infrastructure (Storage, Database, API)",
        stackName: `${stackPrefix}-service`,
    });
});

app.synth();
