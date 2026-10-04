import os
import json
import base64
import hashlib
import tempfile
import pytest
from app.core.secrets import (
    SecretsManager,
    EnvironmentSecretsProvider,
    EncryptedSecretsProvider,
    mask_secret,
    is_sensitive_key,
)


class TestSecretsCore:
    def test_mask_secret(self):
        assert mask_secret(None) == "<EMPTY>"
        assert mask_secret("") == "<EMPTY>"
        assert mask_secret("short") == "********"
        assert mask_secret("1234567") == "********"

        secret = "super_secret_token_123456"
        masked = mask_secret(secret, show_prefix=4, show_suffix=2)
        assert masked == "supe...56"
        assert secret not in masked

    def test_is_sensitive_key(self):
        assert is_sensitive_key("JWT_SECRET") is True
        assert is_sensitive_key("DATABASE_PASSWORD") is True
        assert is_sensitive_key("API_KEY") is True
        assert is_sensitive_key("AUTH_TOKEN") is True
        assert is_sensitive_key("PRIVATE_KEY") is True
        assert is_sensitive_key("CLIENT_CREDENTIALS") is True

        assert is_sensitive_key("PORT") is False
        assert is_sensitive_key("LOG_LEVEL") is False
        assert is_sensitive_key("ENVIRONMENT") is False

    def test_environment_secrets_provider(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY_ENV", "env_secret_val")
        provider = EnvironmentSecretsProvider()

        assert provider.has_secret("TEST_KEY_ENV") is True
        assert provider.get_secret("TEST_KEY_ENV") == "env_secret_val"
        assert provider.has_secret("NON_EXISTENT_KEY") is False
        assert provider.get_secret("NON_EXISTENT_KEY", default="default_val") == "default_val"

    def test_encrypted_secrets_provider(self, monkeypatch):
        from cryptography.fernet import Fernet

        master_key = "test-master-key-32-bytes-long!!"
        derived_key = hashlib.sha256(master_key.encode()).digest()
        f_key = base64.urlsafe_b64encode(derived_key)
        fernet = Fernet(f_key)

        payload = {"SECURE_API_KEY": "encrypted_value_999", "SECRET_DB_PASS": "pass_xyz"}
        encrypted_bytes = fernet.encrypt(json.dumps(payload).encode("utf-8"))

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(encrypted_bytes)
            temp_path = tf.name

        try:
            monkeypatch.setenv("TRUSTDESK_MASTER_KEY", master_key)
            monkeypatch.setenv("TRUSTDESK_SECRETS_FILE", temp_path)

            provider = EncryptedSecretsProvider(secrets_file_path=temp_path)
            assert provider.has_secret("SECURE_API_KEY") is True
            assert provider.get_secret("SECURE_API_KEY") == "encrypted_value_999"
            assert provider.get_secret("SECRET_DB_PASS") == "pass_xyz"
            assert provider.has_secret("UNKNOWN_KEY") is False
            assert provider.get_secret("UNKNOWN_KEY", "fallback") == "fallback"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_encrypted_provider_invalid_key_fails_gracefully(self, monkeypatch):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"garbage_encrypted_data")
            temp_path = tf.name

        try:
            monkeypatch.setenv("TRUSTDESK_MASTER_KEY", "wrong-key")
            monkeypatch.setenv("TRUSTDESK_SECRETS_FILE", temp_path)

            provider = EncryptedSecretsProvider(secrets_file_path=temp_path)
            assert provider.has_secret("ANY_KEY") is False
            assert provider.get_secret("ANY_KEY", "default") == "default"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_secrets_manager_cascading_and_masking(self, monkeypatch):
        monkeypatch.delenv("TRUSTDESK_MASTER_KEY", raising=False)
        monkeypatch.setenv("JWT_SECRET", "env_provided_jwt_secret_value_1234567890")
        monkeypatch.setenv("TEST_APP_TOKEN", "super_high_entropy_token_xyz987654321")

        manager = SecretsManager()
        assert manager.get("TEST_APP_TOKEN") == "super_high_entropy_token_xyz987654321"
        assert manager.get("NON_EXISTENT", "def") == "def"

        masked = manager.get_masked("TEST_APP_TOKEN")
        assert masked == "supe...21"

        assert "super_high_entropy_token" not in str(manager)
        assert "<SecretsManager: secured>" == repr(manager)

    def test_secrets_manager_validate_security(self, monkeypatch):
        monkeypatch.delenv("TRUSTDESK_MASTER_KEY", raising=False)
        monkeypatch.setenv("JWT_SECRET", "change-me-short")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        manager = SecretsManager()
        res = manager.validate_security(environment="production")
        assert res["is_secure"] is False
        assert any("shorter than 32" in issue for issue in res["issues"])
        assert any("insecure development placeholder" in issue for issue in res["issues"])
        assert any("DATABASE_URL is not configured" in issue for issue in res["issues"])

        monkeypatch.setenv("JWT_SECRET", "a_very_secure_high_entropy_random_production_secret_key_123")
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/trustdesk")

        res_prod = manager.validate_security(environment="production")
        assert res_prod["is_secure"] is True
        assert len(res_prod["issues"]) == 0
