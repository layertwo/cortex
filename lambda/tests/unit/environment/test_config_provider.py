"""Tests for the configuration provider."""

import pytest

from src.environment.config_provider import ConfigProvider, log_level


class TestConfigProvider:
    def test_reads_each_value(self, monkeypatch):
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.setenv("OIDC_ISSUER", "https://idp.example.com/")
        monkeypatch.setenv("OIDC_CLIENT_ID", "cortex")
        monkeypatch.setenv("CORS_ORIGINS", "https://a, https://b ,")

        config = ConfigProvider()

        assert config.aws_region == "eu-west-1"
        assert config.oidc_issuer == "https://idp.example.com"
        assert config.oidc_client_id == "cortex"
        assert config.cors_origins == ["https://a", "https://b"]
        assert config.vaults_table_name == "test-vaults-table"

    def test_missing_required_value_raises(self, monkeypatch):
        monkeypatch.delenv("VAULTS_TABLE_NAME")
        with pytest.raises(KeyError):
            ConfigProvider().vaults_table_name

    def test_metadata_and_blob_credentials_are_independent(self, monkeypatch):
        monkeypatch.setenv("DYNAMODB_ACCESS_KEY_ID", "ddb-key")
        monkeypatch.setenv("DYNAMODB_SECRET_ACCESS_KEY", "ddb-secret")
        monkeypatch.setenv("S3_ACCESS_KEY_ID", "s3-key")
        monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "s3-secret")

        config = ConfigProvider()

        assert config.dynamodb_access_key_id == "ddb-key"
        assert config.dynamodb_secret_access_key == "ddb-secret"
        assert config.s3_access_key_id == "s3-key"
        assert config.s3_secret_access_key == "s3-secret"

    def test_values_are_cached_per_provider(self, monkeypatch):
        config = ConfigProvider()
        assert config.oidc_issuer == ""

        monkeypatch.setenv("OIDC_ISSUER", "https://late.example.com")

        assert config.oidc_issuer == ""
        assert ConfigProvider().oidc_issuer == "https://late.example.com"

    def test_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "debug")
        assert log_level() == "debug"
