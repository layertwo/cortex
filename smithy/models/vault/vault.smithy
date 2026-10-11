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
        UpdateVaultPassword
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
@documentation("Store the encrypted vault name")
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

@http(method: "POST", uri: "/v1/vaults/{vaultId}/password")
@documentation("Replace the vault's VMK envelopes after a vault password change")
operation UpdateVaultPassword {
    input: UpdateVaultPasswordInput
    output: UpdateVaultPasswordOutput
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

    @required
    @documentation("Vault creation timestamp")
    createdAt: Timestamp

    @required
    @documentation("Last modified timestamp")
    updatedAt: Timestamp

    @required
    @documentation("Current VMK version")
    currentVmkVersion: Integer

    @required
    @documentation("Current envelope version (increments on each password change)")
    envelopeVersion: Integer

    @required
    @documentation("VMK envelopes, one per vault password generation")
    vmkEnvelopes: VmkEnvelopeList

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
    @documentation("ACQUIRE to lock; RELEASE to commit the re-keyed envelopes")
    action: RotationAction

    @documentation("Expected current rotation state; required for RELEASE (its conditional-write guard), ignored by ACQUIRE")
    expectedState: RotationState

    @documentation("Expected current envelope version (conditional write guard)")
    expectedEnvelopeVersion: Integer

    @documentation("New VMK version to enrol on ACQUIRE; must equal the current version plus one")
    newVmkVersion: Integer

    @documentation("New VMK wrapped under the re-keyed vault key, appended on ACQUIRE")
    wrappedNewVmk: Blob

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

    @required
    @documentation("Current VMK version after the operation")
    currentVmkVersion: Integer

    @required
    @documentation("Current envelope version after the operation")
    envelopeVersion: Integer
}

structure UpdateVaultPasswordInput {
    @required
    @httpLabel
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Expected current envelope version (conditional write guard)")
    expectedEnvelopeVersion: Integer

    @required
    @documentation("VMK envelopes, one per vault password generation")
    vmkEnvelopes: VmkEnvelopeList
}

structure UpdateVaultPasswordOutput {
    @required
    @documentation("New envelope version")
    envelopeVersion: Integer
}
