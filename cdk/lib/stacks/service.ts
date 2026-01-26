import {Construct} from "constructs";

import {Duration, RemovalPolicy, Stack, StackProps} from "aws-cdk-lib";
import {
    AuthorizationType,
    CognitoUserPoolsAuthorizer,
    Cors,
    EndpointType,
    LambdaIntegration,
    MethodLoggingLevel,
    Period,
    RestApi,
} from "aws-cdk-lib/aws-apigateway";
import {UserPool, UserPoolClient} from "aws-cdk-lib/aws-cognito";
import {
    AttributeType,
    Billing,
    ProjectionType,
    TableEncryptionV2,
    TablePropsV2,
    TableV2,
} from "aws-cdk-lib/aws-dynamodb";
import {Code, Function as Lambda, Runtime} from "aws-cdk-lib/aws-lambda";
import {LogGroup, RetentionDays} from "aws-cdk-lib/aws-logs";
import {
    BlockPublicAccess,
    Bucket,
    BucketEncryption,
    HttpMethods,
    StorageClass,
} from "aws-cdk-lib/aws-s3";

import {StageConfig} from "../config";

// Default props shared across all DynamoDB tables
const DYNAMODB_DEFAULT_PROPS: Partial<TablePropsV2> = {
    billing: Billing.onDemand(),
    encryption: TableEncryptionV2.awsManagedKey(),
    pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
    },
    removalPolicy: RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE,
} as const;

export interface ServiceStackProps extends StackProps {
    stage: StageConfig;
    userPool: UserPool;
    userPoolClient: UserPoolClient;
}

export class ServiceStack extends Stack {
    private readonly props: ServiceStackProps;

    public readonly bucket: Bucket;

    // Main data table for authenticated user data
    public readonly dataTable: TableV2;
    // Separate shares table for anonymous access
    public readonly sharesTable: TableV2;

    public readonly apiHandler: Lambda;
    public readonly api: RestApi;

    constructor(scope: Construct, id: string, props: ServiceStackProps) {
        super(scope, id, props);
        this.props = props;

        // Create storage bucket
        this.bucket = this.createStorage();

        // Create database tables
        this.dataTable = this.createDataTable();
        this.sharesTable = this.createSharesTable();

        // Create API resources
        this.apiHandler = this.createApiHandler();
        this.api = this.createApiGateway();
    }

    private resourceName(suffix: string): string {
        return `${this.stackName}-${suffix}`;
    }

    private createStorage(): Bucket {
        // S3 bucket for encrypted file storage
        // Requirements: 1.3, 7.4, 7.5
        return new Bucket(this, "StorageBucket", {
            bucketName: this.resourceName("storage-bucket"),
            encryption: BucketEncryption.S3_MANAGED,
            versioned: true,
            blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
            cors: [
                {
                    allowedMethods: [
                        HttpMethods.GET,
                        HttpMethods.PUT,
                        HttpMethods.POST,
                        HttpMethods.DELETE,
                    ],
                    allowedOrigins: ["*"], // TODO: Restrict to specific origins in production
                    allowedHeaders: ["*"],
                    exposedHeaders: ["ETag"],
                    maxAge: 3000,
                },
            ],
            lifecycleRules: [
                {
                    // Transition to Glacier Instant Retrieval after 30 days of no access
                    id: "transition-to-ia",
                    enabled: true,
                    transitions: [
                        {
                            storageClass: StorageClass.INFREQUENT_ACCESS,
                            transitionAfter: Duration.days(7),
                        },
                    ],
                },
                {
                    // Transition to Glacier Instant Retrieval after 30 days of no access
                    id: "transition-to-glacier",
                    enabled: true,
                    transitions: [
                        {
                            storageClass: StorageClass.GLACIER_INSTANT_RETRIEVAL,
                            transitionAfter: Duration.days(30),
                        },
                    ],
                },
                {
                    // Delete incomplete multipart uploads after 7 days
                    id: "cleanup-incomplete-uploads",
                    enabled: true,
                    abortIncompleteMultipartUploadAfter: Duration.days(7),
                },
            ],
            transferAcceleration: true,
            enforceSSL: true,
            minimumTLSVersion: 1.2,
            removalPolicy: RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE,
        });
    }

    private createDataTable(): TableV2 {
        // Main data table for authenticated user data using single-table design
        // Requirements: 2.5, 6.5, 11.3, 12.2, 19.1, 22.1, 22.2
        const table = new TableV2(this, "DataTable", {
            tableName: this.resourceName("data"),
            partitionKey: {
                name: "PK",
                type: AttributeType.STRING,
            },
            sortKey: {
                name: "SK",
                type: AttributeType.STRING,
            },
            ...DYNAMODB_DEFAULT_PROPS,
        });

        // GSI1: Multi-purpose index for tag search and reverse collection lookup
        table.addGlobalSecondaryIndex({
            indexName: "GSI1",
            partitionKey: {
                name: "GSI1PK",
                type: AttributeType.STRING,
            },
            sortKey: {
                name: "GSI1SK",
                type: AttributeType.STRING,
            },
            projectionType: ProjectionType.ALL,
        });

        return table;
    }

    private createSharesTable(): TableV2 {
        // Shares table - separate for anonymous access security isolation
        // PK: SHARE#{shareId}, SK: METADATA
        // Stores: shareId, fileId, vaultId, userId, createdAt, expiresAt,
        //         isPasswordProtected, isRevoked, accessCount, lastAccessedAt
        //
        // Note: Share key is NOT stored (embedded in URL fragment)
        // Requirements: 17.3
        return new TableV2(this, "SharesTable", {
            tableName: this.resourceName("shares"),
            partitionKey: {
                name: "PK",
                type: AttributeType.STRING,
            },
            sortKey: {
                name: "SK",
                type: AttributeType.STRING,
            },
            ...DYNAMODB_DEFAULT_PROPS,
        });
    }

    private createApiHandler(): Lambda {
        // Single Lambda function for all API routes
        // Requirements: 3.4, 6.1, 6.2, 6.4, 8.2
        const resourceName = this.resourceName("api-handler");
        const fn = new Lambda(this, "ApiHandler", {
            functionName: resourceName,
            runtime: Runtime.PYTHON_3_11,
            handler: "handler.lambda_handler",
            code: Code.fromAsset("../lambda/src/api"),
            environment: {
                STAGE: this.props.stage.stageType,
                DATA_TABLE: this.dataTable.tableName,
                SHARES_TABLE: this.sharesTable.tableName,
                BUCKET_NAME: this.bucket.bucketName,
                USER_POOL_ID: this.props.userPool.userPoolId,
                USER_POOL_CLIENT_ID: this.props.userPoolClient.userPoolClientId,
                POWERTOOLS_SERVICE_NAME: "cortex-api",
                POWERTOOLS_METRICS_NAMESPACE: "Cortex",
                LOG_LEVEL: "INFO",
            },
            timeout: Duration.seconds(30),
            memorySize: 512,
            logGroup: new LogGroup(this, "ApiLogGroup", {
                retention: RetentionDays.ONE_MONTH,
                logGroupName: resourceName,
            }),
        });

        // Grant Lambda permissions to DynamoDB tables
        this.dataTable.grantReadWriteData(fn);
        this.sharesTable.grantReadWriteData(fn);

        this.bucket.grantReadWrite(fn);
        this.bucket.grantDelete(fn);

        return fn;
    }

    private createApiGateway(): RestApi {
        // API Gateway with REST API
        // Requirements: 6.2, 8.2
        const api = new RestApi(this, "Api", {
            restApiName: this.resourceName("api"),
            deployOptions: {
                stageName: "v1",
                loggingLevel: MethodLoggingLevel.INFO,
                dataTraceEnabled: false, // Don't log request/response bodies (encrypted data)
                metricsEnabled: true,
                throttlingBurstLimit: 5000,
                throttlingRateLimit: 2000,
            },

            defaultCorsPreflightOptions: {
                allowOrigins: Cors.ALL_ORIGINS, // TODO: Restrict in production
                allowMethods: Cors.ALL_METHODS,
                allowHeaders: [
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                ],
                maxAge: Duration.hours(1),
            },

            // CloudWatch role for API Gateway logging
            cloudWatchRole: true,

            // Endpoint configuration
            endpointConfiguration: {
                types: [EndpointType.EDGE],
            },
        });

        // Cognito authorizer for API Gateway
        // Requirements: 3.4
        const authorizer = new CognitoUserPoolsAuthorizer(this, "CognitoAuthorizer", {
            cognitoUserPools: [this.props.userPool],
            authorizerName: "CognitoAuthorizer",
            identitySource: "method.request.header.Authorization",
        });

        // Lambda integration with proxy
        const lambdaIntegration = new LambdaIntegration(this.apiHandler, {
            proxy: true,
            allowTestInvoke: true,
        });

        // Recovery endpoint with stricter rate limiting (to prevent brute force attacks)
        // Requirements: 19.1, 19.2 - Security requirement for account recovery
        const recoveryResource = api.root.addResource("recovery");
        const validateCodeResource = recoveryResource.addResource("validate");
        const validateCodeMethod = validateCodeResource.addMethod("POST", lambdaIntegration, {
            // No authorizer - this is used during account recovery
            authorizationType: AuthorizationType.NONE,
            // Strict rate limiting: 10 requests/second, 20 burst
            // This prevents brute force attacks on recovery codes
            methodResponses: [
                {statusCode: "200"},
                {statusCode: "400"},
                {statusCode: "429"}, // Too Many Requests
                {statusCode: "500"},
            ],
        });

        // Add proxy resource to handle all other routes
        // The Lambda function will handle routing internally using APIGatewayRestResolver
        api.root.addProxy({
            defaultIntegration: lambdaIntegration,
            anyMethod: true,
            defaultMethodOptions: {
                authorizer: authorizer,
                authorizationType: AuthorizationType.COGNITO,
            },
        });

        // Usage plan for rate limiting
        const usagePlan = api.addUsagePlan("UsagePlan", {
            name: this.resourceName("usage-plan"),
            description: "Usage plan for Cortex API",
            throttle: {
                rateLimit: 2000,
                burstLimit: 5000,
            },
            quota: {
                limit: 1000000,
                period: Period.MONTH,
            },
        });

        usagePlan.addApiStage({
            stage: api.deploymentStage,
        });

        // Stricter usage plan for recovery endpoints
        // Requirements: 19.1, 19.2 - Prevent brute force attacks on recovery codes
        const recoveryUsagePlan = api.addUsagePlan("RecoveryUsagePlan", {
            name: this.resourceName("recovery-usage-plan"),
            description: "Strict usage plan for recovery endpoints to prevent brute force",
            throttle: {
                rateLimit: 10, // 10 requests per second
                burstLimit: 20, // Allow small bursts
            },
            quota: {
                limit: 1000, // 1000 attempts per month per IP
                period: Period.MONTH,
            },
        });

        recoveryUsagePlan.addApiStage({
            stage: api.deploymentStage,
            throttle: [
                {
                    method: validateCodeMethod,
                    throttle: {
                        rateLimit: 10,
                        burstLimit: 20,
                    },
                },
            ],
        });

        return api;
    }
}
