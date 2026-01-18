$version: "2.0"

namespace layertwo.cortex

// ============================================================================
// Tag Resource
// ============================================================================
@documentation("Tag search resource")
resource Tag {
    operations: [
        SearchByTag
    ]
}

// ============================================================================
// Tag Operations
// ============================================================================
@http(method: "GET", uri: "/v1/tags/search")
@documentation("Search items by encrypted tag")
@readonly
operation SearchByTag {
    input: SearchByTagInput
    output: SearchByTagOutput
    errors: [
        AuthenticationError
        AuthorizationError
        ValidationError
        InternalError
    ]
}

// ============================================================================
// Input/Output Structures
// ============================================================================
structure SearchByTagInput {
    @required
    @httpQuery("vaultId")
    @documentation("Vault identifier")
    vaultId: String

    @required
    @httpQuery("encryptedTag")
    @documentation("Encrypted tag to search for")
    encryptedTag: String

    @httpQuery("pageSize")
    @documentation("Number of items per page (10-100)")
    @range(min: 10, max: 100)
    pageSize: Integer = 50

    @httpQuery("nextToken")
    @documentation("Pagination token from previous response")
    nextToken: String
}

structure SearchByTagOutput {
    @required
    @documentation("List of items matching the encrypted tag")
    items: ItemList

    @documentation("Token for next page of results")
    nextToken: String

    @required
    @documentation("Total count of matching items")
    totalCount: Integer
}
