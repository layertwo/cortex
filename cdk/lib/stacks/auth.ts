import {Construct} from "constructs";

import {Duration, RemovalPolicy, Stack, StackProps} from "aws-cdk-lib";
import {
    AccountRecovery,
    Mfa,
    OAuthScope,
    UserPool,
    UserPoolClient,
    UserPoolEmail,
    VerificationEmailStyle,
} from "aws-cdk-lib/aws-cognito";

import {StageConfig} from "../config";

export interface AuthStackProps extends StackProps {
    stage: StageConfig;
}

export class AuthStack extends Stack {
    public readonly userPool: UserPool;
    public readonly userPoolClient: UserPoolClient;

    constructor(scope: Construct, id: string, props: AuthStackProps) {
        super(scope, id, props);

        // Create authentication components
        this.userPool = this.createUserPool();
        this.userPoolClient = this.createUserPoolClient();
    }

    private resourceName(suffix: string): string {
        return `${this.stackName}-${suffix}`;
    }

    private createUserPool(): UserPool {
        // Cognito User Pool for account password authentication
        // Requirements: 3.1, 3.2, 19.2, 21.1, 21.2
        return new UserPool(this, "UserPool", {
            userPoolName: this.resourceName("user-pool"),

            // Email as username
            signInAliases: {
                email: true,
                username: false,
            },

            // Self sign-up enabled (Amplify-driven signups)
            selfSignUpEnabled: true,

            // Email verification required
            autoVerify: {
                email: true,
            },

            // Password policy - Requirements: 21.1, 21.2
            passwordPolicy: {
                minLength: 12,
                requireLowercase: true,
                requireUppercase: true,
                requireDigits: true,
                requireSymbols: true,
                tempPasswordValidity: Duration.days(7),
            },

            // Account recovery via email
            accountRecovery: AccountRecovery.EMAIL_ONLY,

            // Standard attributes
            standardAttributes: {
                email: {
                    required: true,
                    mutable: true,
                },
            },

            // MFA optional (recommended for users)
            mfa: Mfa.OPTIONAL,
            mfaSecondFactor: {
                sms: true,
                otp: true,
            },

            // Email configuration (use SES in production)
            email: UserPoolEmail.withCognito(),

            // User invitation settings
            userInvitation: {
                emailSubject: "Welcome to Cortex Backup",
                emailBody: "Your temporary password is {####}",
            },

            // User verification settings
            userVerification: {
                emailSubject: "Verify your Cortex Backup account",
                emailBody: "Your verification code is {####}",
                emailStyle: VerificationEmailStyle.CODE,
            },

            // Removal policy
            removalPolicy: RemovalPolicy.RETAIN_ON_UPDATE_OR_DELETE,
        });
    }

    private createUserPoolClient(): UserPoolClient {
        // User Pool Client
        return new UserPoolClient(this, "UserPoolClient", {
            userPool: this.userPool,
            userPoolClientName: this.resourceName("client"),
            generateSecret: false, // public SPA client — Amplify cannot use a client secret

            // Auth flows — SRP only (Amplify default); no custom recovery-code flow
            authFlows: {
                userSrp: true,
            },

            // Token validity
            accessTokenValidity: Duration.hours(1),
            idTokenValidity: Duration.hours(1),
            refreshTokenValidity: Duration.days(30),

            // OAuth settings (for future use)
            oAuth: {
                flows: {
                    authorizationCodeGrant: true,
                },
                scopes: [OAuthScope.EMAIL, OAuthScope.OPENID, OAuthScope.PROFILE],
            },

            // Prevent user existence errors
            preventUserExistenceErrors: true,

            // Enable token revocation
            enableTokenRevocation: true,
        });
    }
}
