$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Authentication Operations (Service-level)
// ============================================================================
@http(method: "POST", uri: "/v1/auth/login")
@documentation("Authenticate user with account password via AWS Cognito")
operation Login {
    input: LoginInput
    output: LoginOutput
    errors: [
        AuthenticationError
        ValidationError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/auth/refresh")
@documentation("Refresh authentication credentials using refresh token")
operation RefreshCredentials {
    input: RefreshCredentialsInput
    output: RefreshCredentialsOutput
    errors: [
        AuthenticationError
        ValidationError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/auth/recover")
@documentation("Initiate account recovery using recovery code")
operation RecoverAccount {
    input: RecoverAccountInput
    output: RecoverAccountOutput
    errors: [
        AuthenticationError
        ValidationError
        RecoveryCodeInvalidError
        InternalError
    ]
}

// ============================================================================
// Input/Output Structures
// ============================================================================
structure LoginInput {
    @required
    @documentation("User email address")
    email: String

    @required
    @documentation("Account password (not vault password)")
    password: String
}

structure LoginOutput {
    @required
    @documentation("Access token for API requests")
    accessToken: String

    @required
    @documentation("Refresh token for obtaining new access tokens")
    refreshToken: String

    @required
    @documentation("Token expiration timestamp")
    expiresAt: Timestamp

    @required
    @documentation("User identifier")
    userId: String
}

structure RefreshCredentialsInput {
    @required
    @documentation("Refresh token from previous login")
    refreshToken: String
}

structure RefreshCredentialsOutput {
    @required
    @documentation("New access token")
    accessToken: String

    @required
    @documentation("New refresh token")
    refreshToken: String

    @required
    @documentation("Token expiration timestamp")
    expiresAt: Timestamp
}

structure RecoverAccountInput {
    @required
    @documentation("User email address")
    email: String

    @required
    @documentation("Account recovery code")
    recoveryCode: String
}

structure RecoverAccountOutput {
    @required
    @documentation("Temporary access token for password reset")
    accessToken: String

    @required
    @documentation("User identifier")
    userId: String

    @documentation("Instructions for completing account recovery")
    message: String
}
