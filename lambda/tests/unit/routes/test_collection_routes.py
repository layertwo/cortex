"""
Unit tests for collection route handlers.

Tests verify that collection routes work correctly through the FastAPI test client.
"""

from botocore.stub import ANY


class TestCreateCollectionRoute:
    """Test suite for CreateCollectionRoute through FastAPI test client."""

    def test_create_collection_route_handler(self, client, dynamodb_stubber, vaults_table_name):
        """Test create collection route handler returns expected response."""
        user_id = "test-user-id"
        vault_id = "test-vault-456"

        # Stub vault ownership check (get_item for vault)
        dynamodb_stubber.add_response(
            "get_item",
            {
                "Item": {
                    "PK": {"S": f"USER#{user_id}"},
                    "SK": {"S": f"VAULT#{vault_id}"},
                    "vault_id": {"S": vault_id},
                    "user_id": {"S": user_id},
                }
            },
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        # Stub DynamoDB put_item call (create collection)
        dynamodb_stubber.add_response(
            "put_item",
            {},
            {
                "TableName": ANY,
                "Item": ANY,
            },
        )

        response = client.post(
            "/v1/collections",
            json={
                "vaultId": vault_id,
                "encryptedMetadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert "collectionId" in body, "Response should include collectionId"
        assert "createdAt" in body, "Response should include createdAt"

        assert isinstance(body["collectionId"], str), "collectionId should be a string"
        assert len(body["collectionId"]) > 0, "collectionId should not be empty"
        # createdAt is an epoch timestamp (number), not an ISO string
        assert isinstance(body["createdAt"], (int, float))

    def test_create_collection_route_handler_missing_vault_id(self, client):
        """Test create collection route handler returns error when vault_id is missing."""
        response = client.post(
            "/v1/collections",
            json={
                "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
            },
        )

        # FastAPI returns 422 for Pydantic validation errors (missing required field)
        assert response.status_code == 422


class TestListCollectionsRoute:
    """Test suite for ListCollectionsRoute through FastAPI test client."""

    def test_list_collections_route_handler_missing_vault_id(self, client):
        """Test list collections route handler returns error when vault_id is missing."""
        response = client.get("/v1/collections")

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422


class TestGetCollectionRoute:
    """Test suite for GetCollectionRoute through FastAPI test client."""

    def test_get_collection_route_handler_missing_vault_id(self, client):
        """Test get collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"

        response = client.get(f"/v1/collections/{collection_id}")

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422


class TestUpdateCollectionRoute:
    """Test suite for UpdateCollectionRoute through FastAPI test client."""

    def test_update_collection_route_handler_missing_vault_id(self, client):
        """Test update collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"

        response = client.put(
            f"/v1/collections/{collection_id}",
            json={
                "encrypted_metadata": "ZW5jcnlwdGVkLW1ldGFkYXRh",
            },
        )

        # FastAPI returns 422 for Pydantic validation errors (missing required field)
        assert response.status_code == 422


class TestDeleteCollectionRoute:
    """Test suite for DeleteCollectionRoute through FastAPI test client."""

    def test_delete_collection_route_handler_missing_vault_id(self, client):
        """Test delete collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"

        response = client.delete(f"/v1/collections/{collection_id}")

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422


class TestAddItemToCollectionRoute:
    """Test suite for AddItemToCollectionRoute through FastAPI test client."""

    def test_add_item_to_collection_route_handler_missing_vault_id(self, client):
        """Test add item to collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"

        response = client.post(
            f"/v1/collections/{collection_id}/items",
            json={
                "item_id": "item-456",
            },
        )

        # FastAPI returns 422 for Pydantic validation errors (missing required field)
        assert response.status_code == 422

    def test_add_item_to_collection_route_handler_missing_item_id(self, client):
        """Test add item to collection route handler returns error when item_id is missing."""
        collection_id = "test-collection-123"

        response = client.post(
            f"/v1/collections/{collection_id}/items",
            json={
                "vault_id": "vault-123",
            },
        )

        # FastAPI returns 422 for Pydantic validation errors (missing required field)
        assert response.status_code == 422


class TestRemoveItemFromCollectionRoute:
    """Test suite for RemoveItemFromCollectionRoute through FastAPI test client."""

    def test_remove_item_from_collection_route_handler_missing_vault_id(self, client):
        """Test remove item from collection route handler returns error when vault_id is missing."""
        collection_id = "test-collection-123"
        item_id = "test-item-456"

        response = client.delete(
            f"/v1/collections/{collection_id}/items/{item_id}",
        )

        # FastAPI returns 422 for missing required query params
        assert response.status_code == 422


class TestCollectionVaultOwnership:
    """Collection routes must reject vaults the caller does not own."""

    def test_create_collection_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"

        # vault_exists -> get_item returns no Item -> False
        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.post(
            "/v1/collections",
            json={"vault_id": vault_id, "encrypted_metadata": "ZW5jcnlwdGVk"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_list_collections_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"

        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.get(f"/v1/collections?vaultId={vault_id}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_get_collection_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"
        collection_id = "test-collection-123"

        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.get(f"/v1/collections/{collection_id}?vaultId={vault_id}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_update_collection_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"
        collection_id = "test-collection-123"

        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.put(
            f"/v1/collections/{collection_id}?vaultId={vault_id}",
            json={"encryptedMetadata": "ZW5j"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_delete_collection_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"
        collection_id = "test-collection-123"

        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.delete(f"/v1/collections/{collection_id}?vaultId={vault_id}")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_add_item_to_collection_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"
        collection_id = "test-collection-123"

        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.post(
            f"/v1/collections/{collection_id}/items?vaultId={vault_id}",
            json={"itemId": "i-1"},
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_remove_item_from_collection_rejects_unowned_vault(
        self, client, dynamodb_stubber, vaults_table_name
    ):
        user_id = "test-user-id"
        vault_id = "someone-elses-vault"
        collection_id = "test-collection-123"
        item_id = "test-item-456"

        dynamodb_stubber.add_response(
            "get_item",
            {},
            {
                "TableName": vaults_table_name,
                "Key": {"PK": f"USER#{user_id}", "SK": f"VAULT#{vault_id}"},
            },
        )

        response = client.delete(
            f"/v1/collections/{collection_id}/items/{item_id}?vaultId={vault_id}"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
