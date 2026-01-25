"""AWS service fixtures with botocore stubbing"""

from typing import Generator
from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber


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


@pytest.fixture
def s3_client(boto_session):
    return boto_session.client("s3")


@pytest.fixture
def s3_stubber(s3_client):
    with Stubber(s3_client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def dynamodb_client(boto_session):
    return boto_session.client("dynamodb")


@pytest.fixture
def dynamodb_resource(boto_session):
    return boto_session.resource("dynamodb")


@pytest.fixture
def dynamodb_stubber(dynamodb_resource):
    with Stubber(dynamodb_resource.meta.client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def dynamodb_table(boto_session, dynamodb_stubber):
    def _dynamo_resource(table_name: str):
        resource = boto_session.resource("dynamodb")
        table = resource.Table(table_name)

        # Replace the Table's internal client with the stubbed one
        table.meta.client = dynamodb_stubber.client

        return table

    return _dynamo_resource


@pytest.fixture(autouse=True)
def boto_session(aws_region_name, aws_access_key_id, aws_secret_access_key, aws_session_token):
    # Load internal service models before creating a boto session
    return boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        region_name=aws_region_name,
    )


@pytest.fixture
def boto_session_patch(boto_session):
    # Libraries are inconsistent about which is used
    with (
        patch("boto3.Session", autospec=True) as m,
        patch("boto3.session.Session", autospec=True) as m2,
    ):
        m.return_value = boto_session
        m2.return_value = boto_session
        yield m


@pytest.fixture(autouse=True)
def boto_resource_patch(
    boto_session, boto_session_patch, dynamodb_client, dynamodb_resource, s3_client
) -> Generator:
    def client(service, *args, **kwargs):
        if service == "dynamodb":
            return dynamodb_client
        if service == "s3":
            return s3_client

        raise ValueError(f"client for {service} not recognized")

    def resource(service, *args, **kwargs):
        if service == "dynamodb":
            return dynamodb_resource

        raise ValueError(f"resource for {service} not recognized")

    with (
        patch.object(boto_session, "resource", resource),
        patch.object(boto_session, "client", client) as m2,
    ):
        yield m2
