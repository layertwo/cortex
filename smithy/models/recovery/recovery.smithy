$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Recovery Resource
// ============================================================================
@documentation("Recovery resource for account recovery")
resource Recovery {
    operations: [
        GenerateRecoveryCodes
        ValidateRecoveryCode
    ]
}

// ============================================================================
// Recovery Operations
// ============================================================================
@http(method: "POST", uri: "/v1/recovery/codes")
@documentation("Generate account recovery codes for user")
operation GenerateRecoveryCodes {
    input: GenerateRecoveryCodesInput
    output: GenerateRecoveryCodesOutput
    errors: [
        AuthenticationError
        AuthorizationError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/recovery/validate")
@documentation("Validate account recovery code")
operation ValidateRecoveryCode {
    input: ValidateRecoveryCodeInput
    output: ValidateRecoveryCodeOutput
    errors: [
        RecoveryCodeInvalidError
        ValidationError
        InternalError
    ]
}

// ============================================================================
// Input/Output Structures
// ============================================================================
structure GenerateRecoveryCodesInput {
    @documentation("Optional flag to regenerate codes")
    regenerate: Boolean = false
}

structure GenerateRecoveryCodesOutput {
    @required
    @documentation("List of 10 recovery codes (format: XXXX-XXXX-XXXX-XXXX)")
    recoveryCodes: RecoveryCodeList

    @required
    @documentation("Generation timestamp")
    generatedAt: Timestamp

    @documentation("Warning message about secure storage")
    message: String
}

structure ValidateRecoveryCodeInput {
    @required
    @documentation("User email address")
    email: String

    @required
    @documentation("Recovery code to validate")
    recoveryCode: String
}

structure ValidateRecoveryCodeOutput {
    @required
    @documentation("Whether the recovery code is valid")
    isValid: Boolean

    @documentation("User identifier if valid")
    userId: String
}
