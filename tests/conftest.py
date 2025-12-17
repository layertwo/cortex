"""
Pytest configuration and shared fixtures for Cortex tests.
"""

import pytest
import os
import sys

# Add lambda directory to Python path for imports
lambda_path = os.path.join(os.path.dirname(__file__), '..', 'lambda')
sys.path.insert(0, lambda_path)


@pytest.fixture
def aws_credentials():
    """Mock AWS credentials for testing."""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_SECURITY_TOKEN'] = 'testing'
    os.environ['AWS_SESSION_TOKEN'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for Lambda functions."""
    os.environ['USERS_TABLE'] = 'test-users-table'
    os.environ['VAULTS_TABLE'] = 'test-vaults-table'
    os.environ['FILES_TABLE'] = 'test-files-table'
    os.environ['COLLECTIONS_TABLE'] = 'test-collections-table'
    os.environ['FILE_COLLECTION_ASSOCIATIONS_TABLE'] = 'test-file-collection-associations-table'
    os.environ['SHARES_TABLE'] = 'test-shares-table'
    os.environ['ACCOUNT_RECOVERY_TABLE'] = 'test-account-recovery-table'
    os.environ['FILES_BUCKET'] = 'test-files-bucket'
    os.environ['POWERTOOLS_SERVICE_NAME'] = 'cortex-test'
    os.environ['LOG_LEVEL'] = 'INFO'
