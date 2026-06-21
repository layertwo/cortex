$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Collection Resource
// ============================================================================
@documentation("Collection resource for organizing items")
resource Collection {
    identifiers: {
        collectionId: String
    }
    create: CreateCollection
    read: GetCollection
    update: UpdateCollection
    delete: DeleteCollection
    list: ListCollections
    operations: [
        AddItemToCollection
        RemoveItemFromCollection
    ]
}

// ============================================================================
// Collection Operations
// ============================================================================
@http(method: "POST", uri: "/v1/collections")
@documentation("Create new collection with encrypted metadata")
operation CreateCollection {
    input: CreateCollectionInput
    output: CreateCollectionOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/collections")
@documentation("List user's collections with item counts")
@readonly
operation ListCollections {
    input: ListCollectionsInput
    output: ListCollectionsOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

@http(method: "GET", uri: "/v1/collections/{collectionId}")
@documentation("Get collection details including associated items")
@readonly
operation GetCollection {
    input: GetCollectionInput
    output: GetCollectionOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        InternalError
    ]
}

@http(method: "PUT", uri: "/v1/collections/{collectionId}")
@documentation("Update collection encrypted metadata")
@idempotent
operation UpdateCollection {
    input: UpdateCollectionInput
    output: UpdateCollectionOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "DELETE", uri: "/v1/collections/{collectionId}")
@documentation("Delete collection while preserving associated items")
@idempotent
operation DeleteCollection {
    input: DeleteCollectionInput
    output: DeleteCollectionOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        InternalError
    ]
}

@http(method: "POST", uri: "/v1/collections/{collectionId}/items")
@documentation("Add item to collection")
operation AddItemToCollection {
    input: AddItemToCollectionInput
    output: AddItemToCollectionOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ResourceNotFoundError
        ValidationError
        InternalError
    ]
}

@http(method: "DELETE", uri: "/v1/collections/{collectionId}/items/{itemId}")
@documentation("Remove item from collection while preserving the item")
@idempotent
operation RemoveItemFromCollection {
    input: RemoveItemFromCollectionInput
    output: RemoveItemFromCollectionOutput
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
structure CreateCollectionInput {
    @required
    @documentation("Vault identifier")
    vaultId: String

    @required
    @documentation("Encrypted collection metadata (name, description, etc.)")
    encryptedMetadata: Blob
}

structure CreateCollectionOutput {
    @required
    @documentation("Collection identifier")
    collectionId: String

    @required
    @documentation("Creation timestamp")
    createdAt: Timestamp
}

structure ListCollectionsInput {
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
    nextToken: String
}

structure ListCollectionsOutput {
    @required
    @documentation("List of collections with encrypted metadata")
    collections: CollectionList

    @documentation("Token for next page of results")
    nextToken: String
}

structure GetCollectionInput {
    @required
    @httpLabel
    @documentation("Collection identifier")
    collectionId: String

    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier (collections are partitioned by vault)")
    vaultId: String
}

structure GetCollectionOutput {
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

    @documentation("List of items in collection")
    items: ItemList
}

structure UpdateCollectionInput {
    @required
    @httpLabel
    @documentation("Collection identifier")
    collectionId: String

    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier (collections are partitioned by vault)")
    vaultId: String

    @required
    @documentation("Updated encrypted collection metadata")
    encryptedMetadata: Blob
}

structure UpdateCollectionOutput {
    @required
    @documentation("Collection identifier")
    collectionId: String

    @required
    @documentation("Update timestamp")
    updatedAt: Timestamp
}

structure DeleteCollectionInput {
    @required
    @httpLabel
    @documentation("Collection identifier")
    collectionId: String

    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier (collections are partitioned by vault)")
    vaultId: String
}

structure DeleteCollectionOutput {
    @required
    @documentation("Deletion confirmation message")
    message: String

    @required
    @documentation("Deletion timestamp")
    deletedAt: Timestamp
}

structure AddItemToCollectionInput {
    @required
    @httpLabel
    @documentation("Collection identifier")
    collectionId: String

    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier (collections are partitioned by vault)")
    vaultId: String

    @required
    @documentation("Item identifier to add")
    itemId: String
}

structure AddItemToCollectionOutput {
    @required
    @documentation("Success message")
    message: String

    @required
    @documentation("Timestamp when item was added")
    addedAt: Timestamp
}

structure RemoveItemFromCollectionInput {
    @required
    @httpLabel
    @documentation("Collection identifier")
    collectionId: String

    @required
    @httpLabel
    @documentation("Item identifier to remove")
    itemId: String

    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier (collections are partitioned by vault)")
    vaultId: String
}

structure RemoveItemFromCollectionOutput {
    @required
    @documentation("Success message")
    message: String

    @required
    @documentation("Removal timestamp")
    removedAt: Timestamp
}
