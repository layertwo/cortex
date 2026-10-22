"""Tests for the service provider's sessions."""

from src.environment.service_provider import ServiceProvider


class TestSessions:
    def test_uses_per_service_credentials_when_set(self, monkeypatch, boto_session_patch):
        monkeypatch.setenv("DYNAMODB_ACCESS_KEY_ID", "ddb-key")
        monkeypatch.setenv("DYNAMODB_SECRET_ACCESS_KEY", "ddb-secret")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "s3-key")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "s3-secret")

        provider = ServiceProvider()
        provider.dynamodb_session
        provider.s3_session

        boto_session_patch.assert_any_call(
            region_name="us-east-1",
            aws_access_key_id="ddb-key",
            aws_secret_access_key="ddb-secret",
        )
        boto_session_patch.assert_any_call(
            region_name="us-east-1",
            aws_access_key_id="s3-key",
            aws_secret_access_key="s3-secret",
        )

    def test_falls_back_to_the_default_session(self):
        provider = ServiceProvider()

        assert provider.dynamodb_session is provider.boto_session
        assert provider.s3_session is provider.boto_session

    def test_default_session_uses_the_configured_region(self, monkeypatch, boto_session_patch):
        monkeypatch.setenv("AWS_REGION", "eu-west-1")

        provider = ServiceProvider()
        provider.boto_session

        boto_session_patch.assert_any_call(region_name="eu-west-1")
