"""
Pytest configuration and shared fixtures for Cortex tests.
"""

from datetime import datetime, timezone

import pytest

from src.environment.service_provider import ServiceProvider
from tests.fixtures.boto import *  # noqa: F403,F401


@pytest.fixture
def now():
    return datetime.now(tz=timezone.utc)


@pytest.fixture
def recovery_table_name():
    return "test-recovery-table"


@pytest.fixture
def vaults_table_name():
    return "test-vaults-table"


@pytest.fixture
def collections_table_name():
    return "test-collections-table"


@pytest.fixture
def items_table_name():
    return "test-items-table"


@pytest.fixture(autouse=True)
def setup_environment(
    monkeypatch,
    aws_region_name,
    aws_access_key_id,
    aws_secret_access_key,
    aws_session_token,
    recovery_table_name,
):
    """Mock environment variables for Lambda functions."""
    monkeypatch.setenv("AWS_REGION", aws_region_name)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", aws_access_key_id)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", aws_secret_access_key)
    monkeypatch.setenv("AWS_SESSION_TOKEN", aws_session_token)
    monkeypatch.setenv("USERS_TABLE_NAME", "test-users-table")
    monkeypatch.setenv("VAULTS_TABLE_NAME", "test-vaults-table")
    monkeypatch.setenv("ITEMS_TABLE_NAME", "test-items-table")
    monkeypatch.setenv("COLLECTIONS_TABLE_NAME", "test-collections-table")
    monkeypatch.setenv("SHARES_TABLE_NAME", "test-shares-table")
    monkeypatch.setenv("RECOVERY_TABLE_NAME", recovery_table_name)
    monkeypatch.setenv("FILES_BUCKET_NAME", "test-files-bucket")


@pytest.fixture
def mock_service_provider():
    return ServiceProvider()
