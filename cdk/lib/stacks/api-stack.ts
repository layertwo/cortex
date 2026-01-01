import {Construct} from "constructs";

import * as cdk from "aws-cdk-lib";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";

export interface ApiStackProps extends cdk.StackProps {
    bucket: s3.IBucket;
    usersTable: dynamodb.ITable;
    vaultsTable: dynamodb.ITable;
    filesTable: dynamodb.ITable;
    collectionsTable: dynamodb.ITable;
    fileCollectionAssociationsTable: dynamodb.ITable;
    sharesTable: dynamodb.ITable;
    accountRecoveryTable: dynamodb.ITable;
    userPool: cognito.IUserPool;
    userPoolClient: cognito.IUserPoolClient;
}

export class ApiStack extends cdk.Stack {
    public readonly apiHandler: lambda.IFunction;
    public readonly api: apigateway.IRestApi;

    constructor(scope: Construct, id: string, props: ApiStackProps) {
        super(scope, id, props);

        // Lambda function and API Gateway will be implemented in task 3.4
        // Placeholder for now
    }
}
