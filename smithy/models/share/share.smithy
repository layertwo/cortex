$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Share Resource
// ============================================================================
@documentation("Share resource for file sharing")
resource Share {
    identifiers: {
        shareId: String
    }
    create: CreateShare
    read: GetShare
    delete: RevokeShare
}

// ============================================================================
// Share Operations
// ============================================================================
@http(method: "POST", uri: "/v1/shares")
@documentation("Create share for item with optional expiration and password protection")
operation CreateShare {
    input: CreateShareInput
    output: CreateShareOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/shares/{shareId}")
@documentation("Access shared item (anonymous access allowed)")
@readonly
operation GetShare {
    input: GetShareInput
    output: GetShareOutput
    errors: [
        ResourceNotFoundError
        ShareExpiredError
        ShareRevokedError
        InternalError
    ]
}

@http(method: "DELETE", uri: "/v1/shares/{shareId}")
@documentation("Revoke share access")
@idempotent
operation RevokeShare {
    input: RevokeShareInput
    output: RevokeShareOutput
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
structure CreateShareInput {
    @required
    @documentation("Item identifier to share")
    itemId: String

    @documentation("Share expiration timestamp (optional)")
    expiresAt: Timestamp

    @documentation("Whether share is password protected")
    isPasswordProtected: Boolean = false
}

structure CreateShareOutput {
    @required
    @documentation("Share identifier")
    shareId: String

    @required
    @documentation("Creation timestamp")
    createdAt: Timestamp

    @documentation("Expiration timestamp")
    expiresAt: Timestamp

    @required
    @documentation("Whether share is password protected")
    isPasswordProtected: Boolean
}

structure GetShareInput {
    @required
    @httpLabel
    @documentation("Share identifier")
    shareId: String
}

structure GetShareOutput {
    @required
    @documentation("Share identifier")
    shareId: String

    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Presigned S3 URL for download")
    downloadUrl: String

    @required
    @documentation("URL expiration timestamp")
    urlExpiresAt: Timestamp

    @required
    @documentation("Encrypted metadata")
    encryptedMetadata: Blob

    @documentation("Share expiration timestamp")
    expiresAt: Timestamp

    @required
    @documentation("Whether share is password protected")
    isPasswordProtected: Boolean
}

structure RevokeShareInput {
    @required
    @httpLabel
    @documentation("Share identifier")
    shareId: String
}

structure RevokeShareOutput {
    @required
    @documentation("Revocation confirmation message")
    message: String

    @required
    @documentation("Revocation timestamp")
    revokedAt: Timestamp
}
