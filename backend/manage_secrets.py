import os
import sys
import argparse
from app.core.secrets import encrypt_secrets, SecretsManager

DEFAULT_SECRETS = {
    "DATABASE_URL": os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/trustdesk"),
    "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "JWT_SECRET": os.getenv("JWT_SECRET", "template-jwt-secret-replace-with-secure-key"),
    "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY", ""),
    "SMTP_USER": os.getenv("SMTP_USER", "admin@trustdesk.local"),
    "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", "template-smtp-password"),
    "SMTP_FROM": os.getenv("SMTP_FROM", "security@trustdesk.local"),
    "CSRF_SECRET_KEY": os.getenv("CSRF_SECRET_KEY", "template-csrf-secret-key-32-bytes"),
}


def build_vault(master_key: str, out_file: str = "secrets.enc"):
    encrypt_secrets(DEFAULT_SECRETS, master_key, out_file)
    print(f"Encrypted vault generated successfully at: {out_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--key", default=os.getenv("TRUSTDESK_MASTER_KEY", "td-master-key-9f8a2c1e4b7d6e5a8c0f3b2e1d4a7c9f"))
    parser.add_argument("--out", default="secrets.enc")
    args = parser.parse_args()
    build_vault(args.key, args.out)
