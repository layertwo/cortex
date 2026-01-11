"""
Pytest configuration and shared fixtures for Cortex tests.
"""

import pytest

from tests.fixtures.boto import *  # noqa: F403,F401


@pytest.fixture(autouse=True)
def setup_environment(
    monkeypatch, aws_region_name, aws_access_key_id, aws_secret_access_key, aws_session_token
):
    """Mock environment variables for Lambda functions."""
    monkeypatch.setenv("AWS_REGION", aws_region_name)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", aws_access_key_id)
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", aws_secret_access_key)
    monkeypatch.setenv("AWS_SESSION_TOKEN", aws_session_token)
    monkeypatch.setenv("USERS_TABLE", "test-users-table")
    monkeypatch.setenv("VAULTS_TABLE", "test-vaults-table")
    monkeypatch.setenv("FILES_TABLE", "test-files-table")
    monkeypatch.setenv("COLLECTIONS_TABLE", "test-collections-table")
    monkeypatch.setenv(
        "FILE_COLLECTION_ASSOCIATIONS_TABLE", "test-file-collection-associations-table"
    )
    monkeypatch.setenv("SHARES_TABLE", "test-shares-table")
    monkeypatch.setenv("ACCOUNT_RECOVERY_TABLE", "test-account-recovery-table")
    monkeypatch.setenv("FILES_BUCKET", "test-files-bucket")
