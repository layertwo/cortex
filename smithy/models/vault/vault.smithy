$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Vault Resource
// ============================================================================
@documentation("Vault resource for managing encrypted data containers")
resource Vault {
    identifiers: {
        vaultId: String
    }
    create: CreateVault
    read: GetVault
    operations: [
        GetVaultSalt
        UpdateVaultRotation
    ]
}

// ============================================================================
// Vault Operations
// ============================================================================
@http(method: "POST", uri: "/v1/vaults")
@documentation("Create new vault with unique vault salt for key derivation")
operation CreateVault {
    input: CreateVaultInput
    output: CreateVaultOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/vaults/{vaultId}")
@documentation("Get vault details")
@readonly
operation GetVault {
    input: GetVaultInput
    output: GetVaultOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/vaults/{vaultId}/salt")
@documentation("Retrieve vault salt for key derivation on new devices")
@readonly
operation GetVaultSalt {
    input: GetVaultSaltInput
    output: GetVaultSaltOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        InternalError
    ]
}

// ============================================================================
// Input/Output Structures
// ============================================================================
structure CreateVaultInput {
    @documentation("Optional vault name (encrypted client-side)")
    encryptedName: Blob
}

structure CreateVaultOutput {
    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Vault salt for key derivation (16 bytes, non-secret)")
    vaultSalt: Blob

    @required
    @documentation("Vault creation timestamp")
    createdAt: Timestamp
}

structure GetVaultInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String
}

structure GetVaultOutput {
    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Vault salt for key derivation (16 bytes, non-secret)")
    vaultSalt: Blob

    @documentation("Encrypted vault name")
    encryptedName: Blob

    @required
    @documentation("Vault creation timestamp")
    createdAt: Timestamp

    @required
    @documentation("Last modified timestamp")
    updatedAt: Timestamp

    @documentation("Current KEK version (increments on each completed rotation)")
    kekVersion: Integer

    @documentation("Current rotation state")
    rotationState: RotationState

    @documentation("Timestamp when rotation lock was acquired (epoch seconds)")
    rotationLockedAt: Long
}

structure GetVaultSaltInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String
}

structure GetVaultSaltOutput {
    @required
    @documentation("Vault salt for key derivation (16 bytes, non-secret)")
    vaultSalt: Blob
}

@http(method: "POST", uri: "/v1/vaults/{vaultId}/rotation")
@documentation("Acquire or release the rotation lock on a vault (conditional write)")
operation UpdateVaultRotation {
    input: UpdateVaultRotationInput
    output: UpdateVaultRotationOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ConflictError
        InternalError
    ]
}

structure UpdateVaultRotationInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("ACQUIRE to lock for rotation; RELEASE to unlock after completion")
    action: RotationAction

    @required
    @documentation("Expected current rotation state (conditional write guard)")
    expectedState: RotationState

    @documentation("New KEK version to write on RELEASE")
    kekVersion: Integer

    @documentation("Re-encrypted vault verifier to persist on RELEASE")
    newVerifier: Blob
}

structure UpdateVaultRotationOutput {
    @required
    @documentation("New rotation state")
    rotationState: RotationState

    @documentation("When the lock was acquired (epoch seconds)")
    rotationLockedAt: Long
}
