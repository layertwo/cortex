"""
Pytest configuration and shared fixtures for Cortex tests.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from src.api.services.collection_service import CollectionService
from src.api.services.item_service import ItemService
from src.api.services.share_service import ShareService
from src.api.services.vault_service import VaultService
from src.environment.service_provider import ServiceProvider
from src.shared.auth import get_current_user
from tests.fixtures.boto import *  # noqa: F403,F401


@pytest.fixture
def now():
    return datetime.now(tz=timezone.utc)


@pytest.fixture
def vaults_table_name():
    return "test-vaults-table"


@pytest.fixture
def collections_table_name():
    return "test-collections-table"


@pytest.fixture
def items_table_name():
    return "test-items-table"


@pytest.fixture
def shares_table_name():
    return "test-shares-table"


@pytest.fixture
def files_bucket_name():
    return "test-files-bucket"


@pytest.fixture(autouse=True)
def setup_environment(
    monkeypatch,
    aws_region_name,
    aws_access_key_id,
    aws_secret_access_key,
    aws_session_token,
    vaults_table_name,
    items_table_name,
    collections_table_name,
    shares_table_name,
    files_bucket_name,
):
    """Mock environment variables for Lambda functions."""
    monkeypatch.setenv("AWS_REGION", aws_region_name)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", aws_access_key_id)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", aws_secret_access_key)
    monkeypatch.setenv("AWS_SESSION_TOKEN", aws_session_token)
    monkeypatch.setenv("VAULTS_TABLE_NAME", vaults_table_name)
    monkeypatch.setenv("ITEMS_TABLE_NAME", items_table_name)
    monkeypatch.setenv("COLLECTIONS_TABLE_NAME", collections_table_name)
    monkeypatch.setenv("SHARES_TABLE_NAME", shares_table_name)
    monkeypatch.setenv("FILES_BUCKET_NAME", files_bucket_name)


@pytest.fixture
def mock_service_provider():
    return ServiceProvider()


@pytest.fixture
def collection_service(boto_session, collections_table_name, items_table_name):
    """Create collection service with stubbed boto3 session."""
    return CollectionService(
        session=boto_session,
        collections_table_name=collections_table_name,
        items_table_name=items_table_name,
    )


@pytest.fixture
def vault_service(boto_session, vaults_table_name):
    """Create a VaultService instance with real table resource."""
    return VaultService(session=boto_session, vaults_table_name=vaults_table_name)


@pytest.fixture
def item_service(boto_session, items_table_name, files_bucket_name):
    """Create an ItemService instance for testing."""
    return ItemService(
        session=boto_session,
        items_table_name=items_table_name,
        s3_bucket_name=files_bucket_name,
    )


@pytest.fixture
def share_service(boto_session, shares_table_name, items_table_name, files_bucket_name):
    """Create a ShareService instance for testing."""
    return ShareService(
        session=boto_session,
        shares_table_name=shares_table_name,
        items_table_name=items_table_name,
        s3_bucket_name=files_bucket_name,
    )


@pytest.fixture
def app(mock_service_provider):
    """Create FastAPI test app via ServiceProvider."""
    app = mock_service_provider.app
    app.dependency_overrides[get_current_user] = lambda: "test-user-id"
    return app


@pytest.fixture
def client(app):
    """FastAPI test client."""
    return TestClient(app)
