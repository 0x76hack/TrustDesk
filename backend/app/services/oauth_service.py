import os
import time
import base64
import hashlib
import hmac
import secrets
import json
import logging
from typing import Tuple, Dict, Any, Optional
from fastapi import HTTPException, status
from app.config import settings

logger = logging.getLogger("trustdesk.oauth")


def generate_pkce_challenge() -> Tuple[str, str]:
    verifier_bytes = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode("ascii")

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    return code_verifier, code_challenge


def generate_oauth_state(provider: str = "corporate_oidc") -> str:
    payload = {
        "provider": provider,
        "nonce": secrets.token_hex(16),
        "created_at": time.time(),
        "expires_at": time.time() + 600,
    }
    payload_json = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("ascii")

    secret = settings.JWT_SECRET.encode("utf-8")
    signature = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).hexdigest()

    return f"{payload_b64}.{signature}"


def verify_oauth_state(state: str) -> Dict[str, Any]:
    if not state or "." not in state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter: malformed token structure.",
        )

    parts = state.split(".", 1)
    payload_b64, signature = parts[0], parts[1]

    secret = settings.JWT_SECRET.encode("utf-8")
    expected_sig = hmac.new(secret, payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, signature):
        logger.warning("OAuth state signature verification failed — possible CSRF attempt.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter: cryptographic signature mismatch.",
        )

    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        data = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OAuth state parameter: unparseable payload.",
        )

    if time.time() > data.get("expires_at", 0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth session has expired. Please initiate login again.",
        )

    return data


def verify_code_verifier(code_verifier: str, expected_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    computed_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return hmac.compare_digest(computed_challenge, expected_challenge)


_pkce_store: Dict[str, Tuple[str, float]] = {}


def store_pkce_verifier(state: str, verifier: str, ttl: int = 600) -> None:
    now = time.time()
    if len(_pkce_store) > 500:
        expired = [k for k, (_, exp) in _pkce_store.items() if now > exp]
        for k in expired:
            _pkce_store.pop(k, None)
    _pkce_store[state] = (verifier, now + ttl)


def retrieve_pkce_verifier(state: str) -> Optional[str]:
    item = _pkce_store.pop(state, None)
    if not item:
        return None
    verifier, expires_at = item
    if time.time() > expires_at:
        return None
    return verifier

