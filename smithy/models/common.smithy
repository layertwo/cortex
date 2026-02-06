$version: "2.0"

namespace layertwo.cortex

/// Type of item stored in the vault
enum ItemType {
    @documentation("Media file (photo, video, document) stored in S3")
    MEDIA = "MEDIA"

    @documentation("Text note with optional rich formatting stored inline")
    NOTE = "NOTE"

    @documentation("Task/to-do item with optional due date stored inline")
    TASK = "TASK"

    @documentation("Calendar event with start/end times stored inline")
    EVENT = "EVENT"
}

/// List of encrypted tags
@length(max: 50)
list EncryptedTagList {
    member: Blob
}

/// List of recovery codes
list RecoveryCodeList {
    member: String
}

/// List of items
list ItemList {
    member: ItemData
}

/// List of collections
list CollectionList {
    member: CollectionData
}

/// List of validation errors
list ValidationErrorList {
    member: ValidationErrorDetail
}

/// Common item data structure
structure ItemData {
    @required
    @documentation("Item identifier")
    itemId: String

    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Item type")
    itemType: ItemType

    @required
    @documentation("Encrypted item content")
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

/// Collection data structure
structure CollectionData {
    @required
    @documentation("Collection identifier")
    collectionId: String

    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Encrypted collection metadata")
    encryptedMetadata: Blob

    @required
    @documentation("Number of items in collection")
    itemCount: Integer

    @required
    @documentation("Creation timestamp")
    createdAt: Timestamp

    @required
    @documentation("Last modified timestamp")
    updatedAt: Timestamp
}

/// Validation error detail
structure ValidationErrorDetail {
    @required
    @documentation("Field name that failed validation")
    field: String

    @required
    @documentation("Validation error message")
    message: String
}
