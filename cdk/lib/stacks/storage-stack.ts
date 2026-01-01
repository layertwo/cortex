import {Construct} from "constructs";

import * as cdk from "aws-cdk-lib";
import * as s3 from "aws-cdk-lib/aws-s3";

export class StorageStack extends cdk.Stack {
    public readonly bucket: s3.IBucket;

    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);

        // S3 bucket will be implemented in task 3.1
        // Placeholder for now
    }
}
