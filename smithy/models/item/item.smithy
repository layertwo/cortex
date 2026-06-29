$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Item Resource (Generic for all types: MEDIA, NOTE, TASK, EVENT)
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
        InitiateItemUpload
    ]
    operations: [
        CompleteItemUpload
        GetItemDownloadUrl
        CreateUploadPartUrls
        AbortItemUpload
    ]
}

// ============================================================================
// Item Operations
// ============================================================================
@http(method: "POST", uri: "/v1/items")
@documentation("Create new item of any type (MEDIA, NOTE, TASK, EVENT)")
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

@http(method: "POST", uri: "/v1/items/upload/init")
@documentation("Initialize item upload for MEDIA items and receive presigned S3 URL")
operation InitiateItemUpload {
    input: InitiateItemUploadInput
    output: InitiateItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/items/{itemId}/upload/complete")
@documentation("Mark item upload as complete for MEDIA items")
operation CompleteItemUpload {
    input: CompleteItemUploadInput
    output: CompleteItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/items")
@documentation("List user's items with optional type filtering and pagination")
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

@http(method: "GET", uri: "/v1/items/{itemId}/download")
@documentation("Get presigned S3 URL for downloading MEDIA items")
@readonly
operation GetItemDownloadUrl {
    input: GetItemDownloadUrlInput
    output: GetItemDownloadUrlOutput
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
    @documentation("Item type (MEDIA, NOTE, TASK, EVENT)")
    itemType: ItemType

    @required
    @documentation("Encrypted item content (type-specific JSON)")
    encryptedContent: Blob

    @required
    @documentation("Encrypted metadata (common fields)")
    encryptedMetadata: Blob

    @documentation("List of encrypted tags")
    encryptedTags: EncryptedTagList

    @documentation("Encrypted date bucket for tasks/events (deterministic)")
    encryptedDateBucket: Blob

    @documentation("Plaintext time bucket for server queries (15-min window)")
    timeBucket: String
}

structure CreateItemOutput {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Item type")
    itemType: ItemType

    @required
    @documentation("Creation timestamp")
    createdAt: Timestamp

    @required
    @documentation("Version number for conflict resolution")
    version: Integer
}

structure InitiateItemUploadInput {
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

structure InitiateItemUploadOutput {
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

structure CompleteItemUploadInput {
    @required
    @httpLabel
    @documentation("Item identifier (must be MEDIA type)")
    itemId: String

    @documentation("Multipart upload id (omit for single-PUT uploads)")
    uploadId: String

    @documentation("Uploaded parts to assemble, in order (multipart only)")
    parts: UploadPartList
}

structure CompleteItemUploadOutput {
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

    @httpQuery("itemType")
    @documentation("Filter by item type (optional)")
    itemType: ItemType

    @httpQuery("timeBucket")
    @documentation("Filter by time bucket for tasks/events (optional)")
    timeBucket: String

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

    @required
    @documentation("Item type")
    itemType: ItemType

    @documentation("Encrypted item content (absent for MEDIA items, whose content lives in S3)")
    encryptedContent: Blob

    @required
    @documentation("Encrypted metadata")
    encryptedMetadata: Blob

    @documentation("List of encrypted tags")
    encryptedTags: EncryptedTagList

    @documentation("Encrypted date bucket (for tasks/events)")
    encryptedDateBucket: Blob

    @documentation("Plaintext time bucket (for tasks/events)")
    timeBucket: String

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

    @documentation("Updated encrypted date bucket")
    encryptedDateBucket: Blob

    @documentation("Updated time bucket")
    timeBucket: String

    @documentation("Expected version for optimistic locking")
    expectedVersion: Integer
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

structure GetItemDownloadUrlInput {
    @required
    @httpLabel
    @documentation("Item identifier (must be MEDIA type)")
    itemId: String
}

structure GetItemDownloadUrlOutput {
    @required
    @documentation("Presigned S3 URL for download")
    downloadUrl: String

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

@http(method: "POST", uri: "/v1/items/{itemId}/upload/parts")
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
    @documentation("Item identifier (must be a pending MEDIA upload)")
    itemId: String

    @required
    @documentation("Multipart upload id from InitiateItemUpload")
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

@http(method: "POST", uri: "/v1/items/{itemId}/upload/abort")
@documentation("Abort an in-progress multipart upload and clean up the pending item")
operation AbortItemUpload {
    input: AbortItemUploadInput
    output: AbortItemUploadOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

structure AbortItemUploadInput {
    @required
    @httpLabel
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Multipart upload id to abort")
    uploadId: String
}

structure AbortItemUploadOutput {
    @documentation("Confirmation message")
    message: String
}
