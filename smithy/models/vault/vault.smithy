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
    update: UpdateVault
    delete: DeleteVault
    list: ListVaults
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

@http(method: "GET", uri: "/v1/vaults")
@documentation("List the caller's vaults with the data a device needs to unlock them")
@readonly
operation ListVaults {
    input: ListVaultsInput
    output: ListVaultsOutput
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

@http(method: "PUT", uri: "/v1/vaults/{vaultId}")
@documentation("Store the encrypted vault name and/or the password verifier")
@idempotent
operation UpdateVault {
    input: UpdateVaultInput
    output: UpdateVaultOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        ConflictError
        InternalError
    ]
}

@http(method: "DELETE", uri: "/v1/vaults/{vaultId}")
@documentation("Delete a vault and everything in it. Resumable: each call does a bounded batch and reports progress; call until deletionState is DELETED or the vault answers 404, which means it is already gone.")
@idempotent
operation DeleteVault {
    input: DeleteVaultInput
    output: DeleteVaultOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ConflictError
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

@http(method: "POST", uri: "/v1/vaults/{vaultId}/rotation")
@documentation("Acquire, pause, or release the rotation lock on a vault (conditional write)")
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

// ============================================================================
// Input/Output Structures
// ============================================================================
structure CreateVaultInput {}

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

structure ListVaultsInput {
    @httpQuery("pageSize")
    @documentation("Number of vaults per page (10-100)")
    @range(min: 10, max: 100)
    pageSize: Integer = 50

    @httpQuery("nextToken")
    @documentation("Pagination token from previous response")
    @length(max: 1024)
    nextToken: String
}

structure ListVaultsOutput {
    @required
    @documentation("Vaults owned by the caller, excluding vaults being deleted")
    vaults: VaultSummaryList

    @documentation("Token for next page of results")
    nextToken: String
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

    @documentation("Password verifier ciphertext (owner only)")
    verifier: Blob

    @documentation("New salt staged by an open rotation; present only while rotationState is IN_PROGRESS or PAUSED")
    pendingVaultSalt: Blob

    @documentation("Verifier for the keys derived from pendingVaultSalt, staged with it; present only while rotationState is IN_PROGRESS or PAUSED")
    pendingVerifier: Blob

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

structure UpdateVaultInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String

    @documentation("Vault name encrypted under the vault metadata key")
    @length(min: 1, max: 1024)
    encryptedName: Blob

    @documentation("Password verifier ciphertext")
    @length(min: 1, max: 256)
    verifier: Blob
}

structure UpdateVaultOutput {
    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Update timestamp")
    updatedAt: Timestamp
}

structure DeleteVaultInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String
}

structure DeleteVaultOutput {
    @required
    @documentation("DELETING while work remains; DELETED once the vault row is gone")
    deletionState: DeletionState

    @required
    @documentation("Item rows removed by this call")
    deletedItems: Integer

    @required
    @documentation("Collection rows removed by this call")
    deletedCollections: Integer

    @required
    @documentation("Share rows removed by this call")
    deletedShares: Integer
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

structure UpdateVaultRotationInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("ACQUIRE to lock; PAUSE to record an interrupted sweep; RELEASE to commit")
    action: RotationAction

    @required
    @documentation("Expected current rotation state (conditional write guard)")
    expectedState: RotationState

    @documentation("New KEK version to write on RELEASE; must equal the current version plus one")
    kekVersion: Integer

    @documentation("New verifier. On ACQUIRE, staged together with newVaultSalt (both or neither). On RELEASE, persisted directly only when nothing is staged.")
    @length(min: 1, max: 256)
    newVerifier: Blob

    @documentation("New vault salt (16 bytes) to stage on ACQUIRE together with newVerifier; ignored if a pair is already staged; rejected on RELEASE")
    @length(min: 16, max: 16)
    newVaultSalt: Blob

    @documentation("Vault name re-encrypted under the new metadata key, persisted on RELEASE")
    @length(min: 1, max: 1024)
    newEncryptedName: Blob
}

structure UpdateVaultRotationOutput {
    @required
    @documentation("New rotation state")
    rotationState: RotationState

    @documentation("When the lock was acquired (epoch seconds)")
    rotationLockedAt: Long

    @documentation("The salt the sweep must derive new keys from; returned on ACQUIRE when a pair is staged")
    pendingVaultSalt: Blob

    @documentation("The verifier for those keys; returned with pendingVaultSalt")
    pendingVerifier: Blob
}
