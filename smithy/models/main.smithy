$version: "2.0"

namespace layertwo.cortex

use aws.protocols#restJson1

// Auth is Cognito User Pools: clients send the Cognito JWT as `Authorization:
// Bearer <idToken>`, and API Gateway's CognitoUserPoolsAuthorizer (see
// cdk/lib/stacks/service.ts) validates it. This is HTTP bearer auth, NOT AWS
// SigV4 — modeling it as @sigv4 made the TS SDK codegen emit a SigV4 signer.
@restJson1
@httpBearerAuth
@title("Cortex Backup API")
@documentation("Zero-knowledge cloud-based productivity suite with client-side encryption. All sensitive data is encrypted client-side before transmission.")
service Cortex {
    version: "2024-01-01"
    operations: []
    resources: [
        Vault
        Item
        Collection
        Tag
        Share
    ]
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
        ShareExpiredError
        ShareRevokedError
    ]
}
