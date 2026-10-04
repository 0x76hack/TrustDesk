import time
import base64
import json
import pytest
from fastapi import HTTPException
from app.services.oauth_service import (
    generate_pkce_challenge,
    verify_code_verifier,
    generate_oauth_state,
    verify_oauth_state,
)


class TestOAuthPKCESecurity:
    def test_generate_pkce_challenge_format(self):
        verifier, challenge = generate_pkce_challenge()
        assert len(verifier) >= 43
        assert len(challenge) >= 43
        assert "=" not in challenge

        assert verify_code_verifier(verifier, challenge) is True

    def test_verify_code_verifier_mismatch_fails(self):
        verifier, challenge = generate_pkce_challenge()
        assert verify_code_verifier("wrong_verifier_string_12345678901234567890", challenge) is False

    def test_generate_and_verify_oauth_state_happy_path(self):
        state = generate_oauth_state(provider="okta")
        assert "." in state

        data = verify_oauth_state(state)
        assert data["provider"] == "okta"
        assert "nonce" in data
        assert len(data["nonce"]) == 32
        assert data["expires_at"] > time.time()

    def test_tampered_state_signature_rejected(self):
        state = generate_oauth_state(provider="okta")
        payload_b64, signature = state.split(".", 1)

        tampered_state = f"{payload_b64}tampered.{signature}"
        with pytest.raises(HTTPException) as exc:
            verify_oauth_state(tampered_state)
        assert exc.value.status_code == 400
        assert "signature mismatch" in exc.value.detail

    def test_malformed_state_rejected(self):
        with pytest.raises(HTTPException) as exc1:
            verify_oauth_state("no_dot_at_all_here")
        assert exc1.value.status_code == 400
        assert "malformed" in exc1.value.detail

        with pytest.raises(HTTPException) as exc2:
            verify_oauth_state("")
        assert exc2.value.status_code == 400

    def test_expired_state_rejected(self):
        import hmac
        import hashlib
        from app.config import settings

        payload = {
            "provider": "google",
            "nonce": "testnonce123",
            "created_at": time.time() - 700,
            "expires_at": time.time() - 100,
        }
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("ascii")
        sig = hmac.new(settings.JWT_SECRET.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
        expired_state = f"{payload_b64}.{sig}"

        with pytest.raises(HTTPException) as exc:
            verify_oauth_state(expired_state)
        assert exc.value.status_code == 400
        assert "expired" in exc.value.detail.lower()

    def test_store_and_retrieve_pkce_verifier(self):
        from app.services.oauth_service import store_pkce_verifier, retrieve_pkce_verifier
        state = "state-token-xyz-123"
        verifier = "verifier-secret-987"
        store_pkce_verifier(state, verifier)

        retrieved = retrieve_pkce_verifier(state)
        assert retrieved == verifier

        assert retrieve_pkce_verifier(state) is None

