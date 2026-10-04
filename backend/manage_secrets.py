import os
import sys
import argparse
from app.core.secrets import encrypt_secrets, SecretsManager

DEFAULT_SECRETS = {
    "DATABASE_URL": "postgresql+asyncpg://trustdesk:trustdesk_secret@postgres:5432/trustdesk",
    "REDIS_URL": "redis://redis:6379/0",
    "JWT_SECRET": "trustdesk-production-super-secret-key-replace-in-prod",
    "OPENROUTER_API_KEY": "",
    "SMTP_USER": "admin@trustdesk.local",
    "SMTP_PASSWORD": "change-in-production",
    "SMTP_FROM": "security@trustdesk.local",
    "CSRF_SECRET_KEY": "trustdesk-csrf-secret-key-production-grade",
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
