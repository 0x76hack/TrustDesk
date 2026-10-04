import time
from unittest.mock import patch, AsyncMock
import pytest
from fastapi import HTTPException
from app.services import otp_service
from app.config import settings


class TestOtpSecurityUnit:
    @pytest.fixture(autouse=True)
    def clean_stores(self):
        otp_service._otp_store.clear()
        otp_service._rate_limit_store.clear()
        with patch("app.services.otp_service.get_redis_client", return_value=None):
            yield
        otp_service._otp_store.clear()
        otp_service._rate_limit_store.clear()

    def test_hash_otp_integrity(self):
        hash1 = otp_service._hash_otp("123456")
        hash2 = otp_service._hash_otp("123456")
        hash3 = otp_service._hash_otp("123457")

        assert len(hash1) == 64
        assert hash1 == hash2
        assert hash1 != hash3

    @pytest.mark.asyncio
    async def test_issue_otp_zero_leakage_and_rate_limiting(self):
        identifier = "user:agent@example.com"
        sent_codes = []

        async def capture_smtp(dest, code):
            sent_codes.append((dest, code))
            return True

        with patch("app.services.otp_service.send_smtp_email", side_effect=capture_smtp):
            res = await otp_service.issue_otp(identifier, "agent@example.com")
            assert res["otp_sent"] is True
            assert "code" not in res
            assert "dev_code" not in res
            assert len(sent_codes) == 1
            assert len(sent_codes[0][1]) == 6
            assert sent_codes[0][1].isdigit()

            assert "code" not in otp_service._otp_store[identifier]
            assert "hash" in otp_service._otp_store[identifier]

            with pytest.raises(HTTPException) as exc_info:
                await otp_service.issue_otp(identifier, "agent@example.com")
            assert exc_info.value.status_code == 429
            assert "Rate limit active" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_issue_otp_smtp_failure_raises_503_and_cleans_state(self):
        identifier = "user:fail_smtp@example.com"
        mock_r = AsyncMock()
        with patch.object(settings, "ENVIRONMENT", "production"), patch("app.services.otp_service.get_redis_client", return_value=mock_r), patch("app.services.otp_service.send_smtp_email", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await otp_service.issue_otp(identifier, "fail_smtp@example.com")
            assert exc.value.status_code == 503
            assert "Failed to deliver verification code" in exc.value.detail

            assert identifier not in otp_service._otp_store
            assert identifier not in otp_service._rate_limit_store


    @pytest.mark.asyncio
    async def test_verify_otp_format_validation(self):
        with pytest.raises(HTTPException) as exc1:
            await otp_service.verify_otp("any_user", "123")
        assert exc1.value.status_code == 400
        assert "Invalid code format" in exc1.value.detail

        with pytest.raises(HTTPException) as exc2:
            await otp_service.verify_otp("any_user", "1234567")
        assert exc2.value.status_code == 400

        with pytest.raises(HTTPException) as exc3:
            await otp_service.verify_otp("any_user", "abcdef")
        assert exc3.value.status_code == 400

    @pytest.mark.asyncio
    async def test_verify_otp_max_attempts_lockout(self):
        identifier = "user:lockout_test"
        valid_code = "654321"
        otp_service._otp_store[identifier] = {
            "hash": otp_service._hash_otp(valid_code),
            "email": "lockout@example.com",
            "expires_at": time.time() + 120,
            "attempts": 0,
        }

        for remaining in [4, 3, 2, 1]:
            with pytest.raises(HTTPException) as exc:
                await otp_service.verify_otp(identifier, "111111")
            assert exc.value.status_code == 400
            assert f"{remaining} attempt(s) remaining" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            await otp_service.verify_otp(identifier, "111111")
        assert exc.value.status_code == 400
        assert "0 attempt(s) remaining" in exc.value.detail

        with pytest.raises(HTTPException) as exc:
            await otp_service.verify_otp(identifier, "111111")
        assert exc.value.status_code == 429
        assert "Maximum verification attempts exceeded" in exc.value.detail
        assert identifier not in otp_service._otp_store

    @pytest.mark.asyncio
    async def test_verify_otp_expiration(self):
        identifier = "user:expired_test"
        otp_service._otp_store[identifier] = {
            "hash": otp_service._hash_otp("123456"),
            "email": "expired@example.com",
            "expires_at": time.time() - 10,
            "attempts": 0,
        }

        with pytest.raises(HTTPException) as exc:
            await otp_service.verify_otp(identifier, "123456")
        assert exc.value.status_code == 400
        assert "expired" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_otp_single_use(self):
        identifier = "user:single_use_test"
        valid_code = "789012"
        otp_service._otp_store[identifier] = {
            "hash": otp_service._hash_otp(valid_code),
            "email": "single@example.com",
            "expires_at": time.time() + 120,
            "attempts": 0,
        }

        assert await otp_service.verify_otp(identifier, valid_code) is True

        with pytest.raises(HTTPException) as exc:
            await otp_service.verify_otp(identifier, valid_code)
        assert exc.value.status_code == 400
        assert "expired or was not requested" in exc.value.detail.lower()
