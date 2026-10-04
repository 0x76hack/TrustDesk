import os
import re
import base64
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

logger = logging.getLogger("trustdesk.secrets")

SENSITIVE_KEY_PATTERNS = [
    r"SECRET",
    r"PASSWORD",
    r"KEY",
    r"TOKEN",
    r"PRIVATE",
    r"CREDENTIAL",
    r"AUTH",
]


def is_sensitive_key(key: str) -> bool:
    upper = key.upper()
    return any(re.search(pat, upper) for pat in SENSITIVE_KEY_PATTERNS)


def mask_secret(value: Optional[str], show_prefix: int = 4, show_suffix: int = 2) -> str:
    if not value:
        return "<EMPTY>"
    if len(value) <= show_prefix + show_suffix + 2:
        return "********"
    return f"{value[:show_prefix]}...{value[-show_suffix:]}"


class BaseSecretsProvider(ABC):
    @abstractmethod
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        pass

    @abstractmethod
    def has_secret(self, key: str) -> bool:
        pass


class EnvironmentSecretsProvider(BaseSecretsProvider):
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = os.getenv(key)
        if val is not None:
            return val
        return default

    def has_secret(self, key: str) -> bool:
        return key in os.environ


class EncryptedSecretsProvider(BaseSecretsProvider):
    def __init__(self, secrets_file_path: Optional[str] = None):
        self.secrets_file_path = secrets_file_path or os.getenv("TRUSTDESK_SECRETS_FILE", "secrets.enc")
        self._decrypted_store: Dict[str, str] = {}
        self._loaded = False

    def reload(self):
        self._loaded = False
        self._decrypted_store.clear()
        self._ensure_loaded()

    def _ensure_loaded(self):
        if self._loaded:
            return
        master_key = os.getenv("TRUSTDESK_MASTER_KEY")
        if not master_key:
            return

        resolved_path = None
        for candidate in [
            self.secrets_file_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), self.secrets_file_path),
            os.path.join(os.getcwd(), self.secrets_file_path),
            os.path.join(os.getcwd(), "backend", self.secrets_file_path),
        ]:
            if candidate and os.path.exists(candidate):
                resolved_path = candidate
                break

        if not resolved_path:
            return

        self._loaded = True

        try:
            derived_key = hashlib.sha256(master_key.encode()).digest()
            with open(resolved_path, "rb") as f:
                encrypted_data = f.read()

            try:
                from cryptography.fernet import Fernet
                f_key = base64.urlsafe_b64encode(derived_key)
                fernet = Fernet(f_key)
                decrypted_bytes = fernet.decrypt(encrypted_data)
                import json
                self._decrypted_store = json.loads(decrypted_bytes.decode("utf-8"))
                logger.info(f"Loaded {len(self._decrypted_store)} encrypted secrets from {resolved_path}")
            except Exception as e:
                logger.warning(f"Failed to decrypt secrets store: {e}")
                if os.getenv("ENVIRONMENT") == "production":
                    raise RuntimeError(f"Critical security failure: Failed to decrypt production secrets store: {e}")
        except Exception as e:
            logger.warning(f"Error loading encrypted secrets: {e}")
            if os.getenv("ENVIRONMENT") == "production":
                raise RuntimeError(f"Critical security failure: Error loading production encrypted secrets: {e}")

    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        self._ensure_loaded()
        return self._decrypted_store.get(key, default)

    def has_secret(self, key: str) -> bool:
        self._ensure_loaded()
        return key in self._decrypted_store


class SecretsManager:
    _instance: Optional["SecretsManager"] = None

    def __init__(self):
        self.env_provider = EnvironmentSecretsProvider()
        self.enc_provider = EncryptedSecretsProvider()

    @classmethod
    def get_instance(cls) -> "SecretsManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.env_provider.get_secret(key)
        if val is not None and val != "":
            return val

        if self.enc_provider.has_secret(key):
            val = self.enc_provider.get_secret(key)
            if val is not None and val != "":
                return val

        return default

    def get_masked(self, key: str) -> str:
        val = self.get(key)
        return mask_secret(val)

    def validate_security(self, environment: str = "production") -> Dict[str, Any]:
        issues = []
        jwt_secret = self.get("JWT_SECRET", "")
        if not jwt_secret or len(jwt_secret) < 32:
            issues.append("JWT_SECRET is shorter than 32 characters or missing.")
        if "replace-in-prod" in jwt_secret or "change-me" in jwt_secret:
            if environment == "production":
                issues.append("JWT_SECRET contains insecure development placeholder.")

        db_url = self.get("DATABASE_URL", "")
        if not db_url:
            issues.append("DATABASE_URL is not configured.")

        return {
            "is_secure": len(issues) == 0,
            "issues": issues,
            "provider_in_use": "encrypted" if self.enc_provider.has_secret("JWT_SECRET") else "environment",
        }

    def __repr__(self) -> str:
        return "<SecretsManager: secured>"


secrets_manager = SecretsManager.get_instance()


def encrypt_secrets(secrets: Dict[str, str], master_key: str, output_path: str) -> None:
    from cryptography.fernet import Fernet
    import json
    derived_key = hashlib.sha256(master_key.encode("utf-8")).digest()
    f_key = base64.urlsafe_b64encode(derived_key)
    fernet = Fernet(f_key)
    data = json.dumps(secrets).encode("utf-8")
    encrypted_bytes = fernet.encrypt(data)
    with open(output_path, "wb") as f:
        f.write(encrypted_bytes)
