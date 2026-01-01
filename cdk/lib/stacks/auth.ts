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
import {IdentityPool, UserPoolAuthenticationProvider} from "aws-cdk-lib/aws-cognito-identitypool";
import {FederatedPrincipal, Role} from "aws-cdk-lib/aws-iam";

import {StageConfig} from "../config";

export interface AuthStackProps extends StackProps {
    stage: StageConfig;
}

export class AuthStack extends Stack {
    public readonly userPool: UserPool;
    public readonly userPoolClient: UserPoolClient;
    public readonly identityPool: IdentityPool;
    public readonly authenticatedRole: Role;

    constructor(scope: Construct, id: string, props: AuthStackProps) {
        super(scope, id, props);

        // Create authentication components
        this.userPool = this.createUserPool();
        this.userPoolClient = this.createUserPoolClient();
        this.identityPool = this.createIdentityPool();
        this.authenticatedRole = this.createAuthenticatedRole();
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

            // Self sign-up enabled
            // TODO temp disable signup
            selfSignUpEnabled: false,

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

            // Auth flows
            authFlows: {
                userPassword: true,
                userSrp: true,
                custom: true, // For recovery code authentication
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

    private createIdentityPool(): IdentityPool {
        // Identity Pool for federated identities
        // Requirements: 3.1, 3.2
        const identityPool = new IdentityPool(this, "IdentityPool", {
            identityPoolName: `${this.stackName.replace(/-/g, "_")}_identity_pool`,
            allowUnauthenticatedIdentities: false,
        });
        identityPool.addUserPoolAuthentication(
            new UserPoolAuthenticationProvider({
                userPool: this.userPool,
                userPoolClient: this.userPoolClient,
            }),
        );
        return identityPool;
    }

    private createAuthenticatedRole(): Role {
        // IAM role for authenticated users
        return new Role(this, "AuthenticatedRole", {
            assumedBy: new FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                {
                    StringEquals: {
                        "cognito-identity.amazonaws.com:aud": this.identityPool.identityPoolId,
                    },
                    "ForAnyValue:StringLike": {
                        "cognito-identity.amazonaws.com:amr": "authenticated",
                    },
                },
                "sts:AssumeRoleWithWebIdentity",
            ),
            description: "IAM role for authenticated Cortex users",
        });
    }
}
