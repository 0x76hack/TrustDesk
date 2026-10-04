import time
import secrets
import smtplib
import logging
import asyncio
import hmac
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import redis.asyncio as redis
from app.config import settings

logger = logging.getLogger(__name__)

_otp_store: Dict[str, Dict[str, Any]] = {}
_rate_limit_store: Dict[str, float] = {}

OTP_EXPIRY_SECONDS = 120
RATE_LIMIT_COOLDOWN = 30
MAX_VERIFY_ATTEMPTS = 5

_redis_client: Optional[redis.Redis] = None


def _hash_otp(code: str) -> str:
    secret = settings.JWT_SECRET.encode("utf-8")
    return hmac.new(secret, code.strip().encode("utf-8"), hashlib.sha256).hexdigest()


async def get_redis_client() -> Optional[redis.Redis]:
    global _redis_client
    if _redis_client is None:
        try:
            client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await client.ping()
            _redis_client = client
        except Exception as exc:
            logger.debug(f"Redis unavailable for OTP service ({exc}), using in-memory fallback.")
            _redis_client = None
    return _redis_client


def _send_smtp_email_sync(to_email: str, code: str) -> bool:
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not fully configured (missing host, user, or password). Skipping email dispatch.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your TrustDesk Verification Code: {code}"
        msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
        msg["To"] = to_email

        text_content = (
            f"Hello,\n\n"
            f"Your one-time security verification code for TrustDesk is:\n\n"
            f"    {code}\n\n"
            f"This code will expire in exactly 2 minutes (120 seconds).\n\n"
            f"If you did not request this verification, please contact support immediately.\n\n"
            f"— TrustDesk Operations Team"
        )
        html_content = f"""
        <div style="font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 28px; background-color: #f8fafc; border-radius: 12px; max-width: 480px; margin: 0 auto; border: 1px solid #e2e8f0;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #fc8019; font-size: 24px; font-weight: 800; margin: 0; letter-spacing: -0.5px;">TrustDesk</h1>
                <p style="color: #64748b; font-size: 13px; margin-top: 4px;">Security Verification & MFA</p>
            </div>
            <div style="background-color: #ffffff; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); text-align: center;">
                <p style="font-size: 14px; color: #334155; margin-bottom: 18px; line-height: 1.5;">Use this verification code to complete your login or MFA setup:</p>
                <div style="font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #0f172a; padding: 14px; background-color: #fff7ed; border: 1px dashed #fdba74; text-align: center; border-radius: 8px; margin: 0 auto; display: inline-block;">
                    {code}
                </div>
                <p style="font-size: 12px; color: #ea580c; margin-top: 18px; font-weight: 600;">
                    Expires in 2 minutes (120 seconds)
                </p>
            </div>
            <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 20px; line-height: 1.5;">
                If you did not initiate this request, you can safely ignore this email.
            </p>
        </div>
        """
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
            if settings.SMTP_TLS:
                server.starttls()

        with server:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Successfully dispatched OTP via SMTP to recipient: {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
        return False


async def send_smtp_email(to_email: str, code: str) -> bool:
    return await asyncio.to_thread(_send_smtp_email_sync, to_email, code)


async def issue_otp(identifier: str, destination_email: str, phone: Optional[str] = None) -> Dict[str, Any]:
    now = time.time()
    r = await get_redis_client()

    if settings.ENVIRONMENT == "production" and not r:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable (distributed state offline). Please retry shortly.",
        )

    if r:
        try:
            last_req = await r.get(f"otp_rate:{identifier}")
            if last_req:
                elapsed = now - float(last_req)
                if elapsed < RATE_LIMIT_COOLDOWN:
                    remaining = int(RATE_LIMIT_COOLDOWN - elapsed)
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit active. Please wait {remaining} seconds before requesting a new verification code.",
                    )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Redis rate limit check failed ({e}), checking memory store")
            last_requested = _rate_limit_store.get(identifier, 0)
            elapsed = now - last_requested
            if elapsed < RATE_LIMIT_COOLDOWN:
                remaining = int(RATE_LIMIT_COOLDOWN - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit active. Please wait {remaining} seconds before requesting a new verification code.",
                )
    else:
        last_requested = _rate_limit_store.get(identifier, 0)
        elapsed = now - last_requested
        if elapsed < RATE_LIMIT_COOLDOWN:
            remaining = int(RATE_LIMIT_COOLDOWN - elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit active. Please wait {remaining} seconds before requesting a new verification code.",
            )

    code = f"{secrets.randbelow(900000) + 100000}"
    code_hash = _hash_otp(code)

    if r:
        try:
            await r.set(f"otp:{identifier}", code_hash, ex=OTP_EXPIRY_SECONDS)
            await r.set(f"otp_attempts:{identifier}", "0", ex=OTP_EXPIRY_SECONDS)
            await r.set(f"otp_rate:{identifier}", str(now), ex=RATE_LIMIT_COOLDOWN)
        except Exception as e:
            logger.warning(f"Failed to persist OTP to Redis: {e}")

    _otp_store[identifier] = {
        "hash": code_hash,
        "email": destination_email,
        "phone": phone,
        "expires_at": now + OTP_EXPIRY_SECONDS,
        "attempts": 0,
    }
    _rate_limit_store[identifier] = now

    smtp_success = await send_smtp_email(destination_email, code)
    if not smtp_success:
        if settings.ENVIRONMENT == "production":
            if r:
                try:
                    await r.delete(f"otp:{identifier}")
                    await r.delete(f"otp_attempts:{identifier}")
                    await r.delete(f"otp_rate:{identifier}")
                except Exception:
                    pass
            _otp_store.pop(identifier, None)
            _rate_limit_store.pop(identifier, None)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to deliver verification code email. Please check server SMTP configuration and try again.",
            )
        logger.info(
            f"[DEV OTP DISPATCH] SMTP unavailable. OTP for {destination_email}: {code}"
        )

    logger.info(
        f"[SECURITY OTP DISPATCH] Identifier: {identifier} | Destination: {destination_email} | Expires in: {OTP_EXPIRY_SECONDS}s"
    )

    payload = {
        "otp_sent": True,
        "destination": destination_email,
        "expires_in_seconds": OTP_EXPIRY_SECONDS,
        "message": f"Verification code dispatched to {destination_email}. Valid for 2 minutes."
        if smtp_success
        else f"Verification code generated (dev mode): {code}. Valid for 2 minutes.",
    }
    if not smtp_success and settings.ENVIRONMENT == "development":
        payload["dev_code"] = code
    return payload


async def verify_otp(identifier: str, submitted_code: str) -> bool:
    clean_code = submitted_code.strip()
    if len(clean_code) != 6 or not clean_code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code format. Verification code must be exactly 6 numeric digits.",
        )

    r = await get_redis_client()
    if settings.ENVIRONMENT == "production" and not r:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable (distributed state offline). Please retry shortly.",
        )
    stored_hash: Optional[str] = None
    attempts: int = 0

    if r:
        try:
            stored_hash = await r.get(f"otp:{identifier}")
            att_str = await r.get(f"otp_attempts:{identifier}")
            attempts = int(att_str) if att_str else 0
        except Exception as e:
            logger.warning(f"Failed to read OTP from Redis: {e}")

    if not stored_hash:
        record = _otp_store.get(identifier)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired or was not requested. Please request a new code.",
            )
        now = time.time()
        if now > record["expires_at"]:
            _otp_store.pop(identifier, None)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired (2-minute window exceeded). Please request a new code.",
            )
        stored_hash = record["hash"]
        attempts = record["attempts"]

    attempts += 1

    if attempts > MAX_VERIFY_ATTEMPTS:
        if r:
            try:
                await r.delete(f"otp:{identifier}", f"otp_attempts:{identifier}")
            except Exception:
                pass
        _otp_store.pop(identifier, None)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Maximum verification attempts exceeded. Code has been invalidated. Request a new code.",
        )

    if r:
        try:
            ttl = await r.ttl(f"otp:{identifier}")
            if ttl and ttl > 0:
                await r.set(f"otp_attempts:{identifier}", str(attempts), ex=ttl)
        except Exception:
            pass

    if identifier in _otp_store:
        _otp_store[identifier]["attempts"] = attempts

    submitted_hash = _hash_otp(clean_code)
    if not hmac.compare_digest(submitted_hash, stored_hash):
        remaining = MAX_VERIFY_ATTEMPTS - attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incorrect verification code. {remaining} attempt(s) remaining.",
        )

    if r:
        try:
            await r.delete(f"otp:{identifier}", f"otp_attempts:{identifier}")
        except Exception:
            pass
    _otp_store.pop(identifier, None)
    return True
