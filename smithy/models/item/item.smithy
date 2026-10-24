$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Item Resource (blob and inline items)
// ============================================================================
@documentation("Item resource for managing all types of encrypted items")
resource Item {
    identifiers: {
        itemId: String
    }
    create: CreateItem
    read: GetItem
    update: UpdateItem
    delete: DeleteItem
    list: ListItems
    collectionOperations: [
        CreateItemUpload
    ]
    operations: [
        GetItemUpload
        FinalizeItemUpload
        GetItemContentUrl
        CreateUploadPartUrls
        DeleteItemUpload
    ]
}

// ============================================================================
// Item Operations
// ============================================================================
@http(method: "POST", uri: "/v1/items")
@documentation("Create a new inline item")
operation CreateItem {
    input: CreateItemInput
    output: CreateItemOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/items/upload")
@documentation("Create a blob upload for an item and receive a presigned S3 URL")
operation CreateItemUpload {
    input: CreateItemUploadInput
    output: CreateItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/items/{itemId}/upload")
@documentation("Check whether a blob upload is still pending or complete")
@readonly
operation GetItemUpload {
    input: GetItemUploadInput
    output: GetItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/items/{itemId}/upload/finalize")
@documentation("Verify the uploaded object (assembling multipart parts) and mark it complete")
operation FinalizeItemUpload {
    input: FinalizeItemUploadInput
    output: FinalizeItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/items")
@documentation("List a vault's items with pagination")
@readonly
operation ListItems {
    input: ListItemsInput
    output: ListItemsOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/items/{itemId}")
@documentation("Get encrypted metadata for specific item")
@readonly
operation GetItem {
    input: GetItemInput
    output: GetItemOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        InternalError
    ]
}

@http(method: "PUT", uri: "/v1/items/{itemId}")
@documentation("Update item metadata")
@idempotent
operation UpdateItem {
    input: UpdateItemInput
    output: UpdateItemOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/items/{itemId}/content-url")
@documentation("Get a presigned S3 URL for an item's blob content")
@readonly
operation GetItemContentUrl {
    input: GetItemContentUrlInput
    output: GetItemContentUrlOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "DELETE", uri: "/v1/items/{itemId}")
@documentation("Delete item and associated data")
@idempotent
operation DeleteItem {
    input: DeleteItemInput
    output: DeleteItemOutput
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
structure CreateItemInput {
    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Encrypted item content (type-specific JSON)")
    encryptedContent: Blob

    @required
    @documentation("Encrypted metadata (common fields)")
    encryptedMetadata: Blob

    @documentation("List of encrypted tags")
    encryptedTags: EncryptedTagList
}

structure CreateItemOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Creation timestamp")
    createdAt: Timestamp

    @required
    @documentation("Version number for conflict resolution")
    version: Integer
}

structure CreateItemUploadInput {
    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Encrypted metadata")
    encryptedMetadata: Blob

    @required
    @documentation("File size in bytes (for MEDIA items)")
    @range(min: 1)
    sizeBytes: Long

    @documentation("List of encrypted tags")
    encryptedTags: EncryptedTagList

    @required
    @documentation("Wrapped per-file DEK (97 bytes, HMAC-bound to contentId)")
    wrappedDek: Blob

    @required
    @documentation("KEK version that wrapped the DEK (1 in Phase 1)")
    dekVersion: Integer
}

structure CreateItemUploadOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Presigned S3 URL for upload")
    uploadUrl: String

    @required
    @documentation("URL expiration timestamp (15 minutes)")
    expiresAt: Timestamp

    @documentation("S3 key for the uploaded object")
    s3Key: String

    @documentation("Multipart upload id (present only for files above the multipart threshold)")
    uploadId: String
}

@documentation("Lifecycle of a blob upload")
enum UploadStatus {
    @documentation("The object has not been verified yet")
    PENDING = "PENDING"

    @documentation("The object is present and the item is readable")
    COMPLETE = "COMPLETE"
}

structure GetItemUploadInput {
    @required
    @httpLabel
    @documentation("Item identifier")
    itemId: String
}

structure GetItemUploadOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("PENDING until the object is verified, then COMPLETE")
    status: UploadStatus

    @documentation("When the current presigned upload URLs expire")
    expiresAt: Timestamp
}

structure FinalizeItemUploadInput {
    @required
    @httpLabel
    @documentation("Item identifier (must be a BLOB item)")
    itemId: String

    @documentation("Multipart upload id (omit for single-PUT uploads)")
    uploadId: String

    @documentation("Uploaded parts to assemble, in order (multipart only)")
    parts: UploadPartList
}

structure FinalizeItemUploadOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Upload completion timestamp")
    completedAt: Timestamp

    @documentation("Success message")
    message: String
}

structure ListItemsInput {
    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier")
    vaultId: String

    @httpQuery("pageSize")
    @documentation("Number of items per page (10-100)")
    @range(min: 10, max: 100)
    pageSize: Integer = 50

    @httpQuery("nextToken")
    @documentation("Pagination token from previous response")
    @length(max: 1024)
    nextToken: String
}

structure ListItemsOutput {
    @required
    @documentation("List of items with encrypted metadata")
    items: ItemList

    @documentation("Token for next page of results")
    nextToken: String

    @required
    @documentation("Total count of items (may be approximate)")
    totalCount: Integer
}

structure GetItemInput {
    @required
    @httpLabel
    @documentation("Item identifier")
    itemId: String
}

structure GetItemOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Vault identifier")
    vaultId: String

    @documentation("Encrypted item content (absent for BLOB items, whose content lives in S3)")
    encryptedContent: Blob

    @required
    @documentation("Encrypted metadata")
    encryptedMetadata: Blob

    @documentation("List of encrypted tags")
    encryptedTags: EncryptedTagList

    @documentation("File size in bytes (for MEDIA items)")
    sizeBytes: Long

    @documentation("S3 key (for MEDIA items)")
    s3Key: String

    @documentation("Wrapped per-file DEK (MEDIA items)")
    wrappedDek: Blob

    @documentation("KEK version that wrapped the DEK (MEDIA items)")
    dekVersion: Integer

    @required
    @documentation("Creation timestamp")
    createdAt: Timestamp

    @required
    @documentation("Last modified timestamp")
    updatedAt: Timestamp

    @required
    @documentation("Version number for conflict resolution")
    version: Integer
}

structure UpdateItemInput {
    @required
    @httpLabel
    @documentation("Item identifier")
    itemId: String

    @documentation("Updated encrypted content")
    encryptedContent: Blob

    @documentation("Updated encrypted metadata")
    encryptedMetadata: Blob

    @documentation("Updated encrypted tags")
    encryptedTags: EncryptedTagList

    @documentation("Expected version for optimistic locking")
    expectedVersion: Integer

    @documentation("Re-wrapped DEK under the new KEK (rotation sweep only)")
    wrappedDek: Blob

    @documentation("New KEK version that wrapped the DEK (rotation sweep only)")
    dekVersion: Integer
}

structure UpdateItemOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Update timestamp")
    updatedAt: Timestamp

    @required
    @documentation("New version number")
    version: Integer
}

structure GetItemContentUrlInput {
    @required
    @httpLabel
    @documentation("Item identifier (must be a BLOB item)")
    itemId: String
}

structure GetItemContentUrlOutput {
    @required
    @documentation("Presigned S3 URL for the item's content")
    contentUrl: String

    @required
    @documentation("URL expiration timestamp (15 minutes)")
    expiresAt: Timestamp
}

structure DeleteItemInput {
    @required
    @httpLabel
    @documentation("Item identifier")
    itemId: String
}

structure DeleteItemOutput {
    @required
    @documentation("Deletion confirmation message")
    message: String

    @required
    @documentation("Deletion timestamp")
    deletedAt: Timestamp
}

// ============================================================================
// Multipart upload (large-file streaming, slice 2.5b)
// ============================================================================
@documentation("An uploaded multipart part and its S3 ETag")
structure UploadPart {
    @required
    @documentation("Part number (1-10000)")
    @range(min: 1, max: 10000)
    partNumber: Integer

    @required
    @documentation("S3 ETag returned when the part was uploaded")
    eTag: String
}

list UploadPartList {
    member: UploadPart
}

list PartNumberList {
    member: Integer
}

@documentation("A presigned URL for uploading one multipart part")
structure UploadPartUrl {
    @required
    @documentation("Part number this URL uploads")
    partNumber: Integer

    @required
    @documentation("Presigned S3 URL for this part")
    url: String

    @required
    @documentation("URL expiration timestamp")
    expiresAt: Timestamp
}

list UploadPartUrlList {
    member: UploadPartUrl
}

@http(method: "POST", uri: "/v1/items/{itemId}/upload/part-urls")
@documentation("Mint a batch of presigned URLs for multipart upload parts")
operation CreateUploadPartUrls {
    input: CreateUploadPartUrlsInput
    output: CreateUploadPartUrlsOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

structure CreateUploadPartUrlsInput {
    @required
    @httpLabel
    @documentation("Item identifier (must be a pending BLOB upload)")
    itemId: String

    @required
    @documentation("Multipart upload id from CreateItemUpload")
    uploadId: String

    @required
    @documentation("Part numbers to mint URLs for")
    partNumbers: PartNumberList
}

structure CreateUploadPartUrlsOutput {
    @required
    @documentation("Presigned URLs, one per requested part number")
    urls: UploadPartUrlList
}

@http(method: "DELETE", uri: "/v1/items/{itemId}/upload")
@documentation("Abort a pending upload and delete the pending item")
operation DeleteItemUpload {
    input: DeleteItemUploadInput
    output: DeleteItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

structure DeleteItemUploadInput {
    @required
    @httpLabel
    @documentation("Item identifier")
    itemId: String
}

structure DeleteItemUploadOutput {
    @documentation("Confirmation message")
    message: String
}
