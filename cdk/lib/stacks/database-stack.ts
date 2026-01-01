import {Construct} from "constructs";

import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";

export class DatabaseStack extends cdk.Stack {
    public readonly usersTable: dynamodb.ITable;
    public readonly vaultsTable: dynamodb.ITable;
    public readonly filesTable: dynamodb.ITable;
    public readonly collectionsTable: dynamodb.ITable;
    public readonly fileCollectionAssociationsTable: dynamodb.ITable;
    public readonly sharesTable: dynamodb.ITable;
    public readonly accountRecoveryTable: dynamodb.ITable;

    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // DynamoDB tables will be implemented in task 3.2
        // Placeholder for now
    }
}
