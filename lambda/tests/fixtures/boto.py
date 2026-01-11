import pytest


@pytest.fixture(scope="session")
def aws_region_name():
    return "us-east-1"


@pytest.fixture(scope="session")
def aws_account_id():
    return "00000000000"


@pytest.fixture(scope="session")
def aws_access_key_id():
    return "fake-access-key-id"


@pytest.fixture(scope="session")
def aws_secret_access_key():
    return "fake-secret-access-key"


@pytest.fixture(scope="session")
def aws_session_token():
    return "fake-session-token"
