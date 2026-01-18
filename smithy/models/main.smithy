$version: "2.0"

namespace layertwo.cortex

use aws.auth#sigv4
use aws.protocols#restJson1

@restJson1
@sigv4(name: "cortex")
@title("Cortex Backup API")
@documentation("Zero-knowledge cloud-based productivity suite with client-side encryption. All sensitive data is encrypted client-side before transmission.")
service Cortex {
    version: "2024-01-01"
    operations: [
        // Authentication operations (service-level)
        Login
        RefreshCredentials
        RecoverAccount
    ]
    resources: [
        Vault
        Item
        Collection
        Tag
        Share
        Recovery
    ]
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
        ShareExpiredError
        ShareRevokedError
        RecoveryCodeInvalidError
    ]
}
