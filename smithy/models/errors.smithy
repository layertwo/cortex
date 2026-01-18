$version: "2.0"

namespace layertwo.cortex

@error("client")
@httpError(401)
structure AuthenticationError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "AUTHENTICATION_FAILED"
}

@error("client")
@httpError(403)
structure AuthorizationError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "AUTHORIZATION_FAILED"
}

@error("client")
@httpError(404)
structure ResourceNotFoundError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "RESOURCE_NOT_FOUND"
}

@error("client")
@httpError(400)
structure ValidationError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "INVALID_REQUEST"

    @documentation("List of validation errors")
    errors: ValidationErrorList
}

@error("server")
@httpError(500)
structure InternalError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "INTERNAL_ERROR"

    @documentation("Request ID for debugging")
    requestId: String
}

@error("client")
@httpError(403)
structure ShareExpiredError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "SHARE_EXPIRED"

    @documentation("Share expiration timestamp")
    expiresAt: Timestamp
}

@error("client")
@httpError(403)
structure ShareRevokedError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "SHARE_REVOKED"

    @documentation("Revocation timestamp")
    revokedAt: Timestamp
}

@error("client")
@httpError(400)
structure RecoveryCodeInvalidError {
    @required
    message: String

    @documentation("Error code for client handling")
    code: String = "RECOVERY_CODE_INVALID"
}
