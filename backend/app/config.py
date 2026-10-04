import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from app.core.secrets import secrets_manager


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://trustdesk:trustdesk_secret@localhost:5432/trustdesk",
        description="Async PostgreSQL connection string"
    )

    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string for state, cache, and ARQ queue"
    )

    JWT_SECRET: str = Field(
        default="change-me-to-a-long-random-string-in-production-at-least-32-bytes",
        description="HMAC SHA-256 secret key for signing JWTs"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    CSRF_SECRET_KEY: str = Field(
        default="trustdesk-csrf-secret-key-32-bytes-minimum-entropy",
        description="Secret key for generating and verifying cryptographic CSRF tokens"
    )
    CSRF_COOKIE_NAME: str = "trustdesk_csrf_token"
    ENFORCE_HTTPS: bool = Field(
        default=False,
        description="Whether to enforce strict 301 HTTPS redirection and HSTS"
    )

    OAUTH_ENABLED: bool = False
    OAUTH_PROVIDER: str = "corporate_oidc"
    OAUTH_CLIENT_ID: Optional[str] = None
    OAUTH_CLIENT_SECRET: Optional[str] = None
    OAUTH_DISCOVERY_URL: Optional[str] = None
    OAUTH_REDIRECT_URI: Optional[str] = "http://localhost:5173/auth/callback"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    MODEL_FAST: str = "google/gemini-2.0-flash-001"
    MODEL_CAPABLE: str = "google/gemini-2.5-flash-preview-05-20"
    MODEL_REASONING: str = "google/gemini-2.5-pro-preview-05-06"

    EMBEDDING_MODEL: str = "google/gemini-embedding-exp"
    EMBEDDING_DIM: int = 768

    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"
    LOG_FORMAT: str = "json"

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "security@trustdesk.local"
    SMTP_TLS: bool = True

    TRUSTDESK_MASTER_KEY: Optional[str] = None
    TRUSTDESK_SECRETS_FILE: Optional[str] = "secrets.enc"

    model_config = {
        "env_file": (
            str(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")),
            ".env",
            "backend/.env",
        ),
        "extra": "ignore",
    }

    def __init__(self, **values):
        super().__init__(**values)
        if self.TRUSTDESK_MASTER_KEY:
            os.environ["TRUSTDESK_MASTER_KEY"] = self.TRUSTDESK_MASTER_KEY
        if self.TRUSTDESK_SECRETS_FILE:
            os.environ["TRUSTDESK_SECRETS_FILE"] = self.TRUSTDESK_SECRETS_FILE
            secrets_manager.enc_provider.secrets_file_path = self.TRUSTDESK_SECRETS_FILE
        secrets_manager.enc_provider.reload()

        for sensitive_field in [
            "JWT_SECRET",
            "DATABASE_URL",
            "REDIS_URL",
            "OPENROUTER_API_KEY",
            "SMTP_PASSWORD",
            "SMTP_USER",
            "SMTP_FROM",
            "CSRF_SECRET_KEY",
            "OAUTH_CLIENT_SECRET",
        ]:
            secret_val = secrets_manager.get(sensitive_field)
            if secret_val:
                setattr(self, sensitive_field, secret_val)


settings = Settings()
