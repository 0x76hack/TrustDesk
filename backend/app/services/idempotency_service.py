import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.idempotency import IdempotencyKey
from app.services.otp_service import get_redis_client

logger = logging.getLogger("trustdesk.idempotency")

IDEMPOTENCY_DEFAULT_TTL_SECONDS = 86400


async def check_idempotency(
    key: str,
    entity_type: str,
    db: AsyncSession,
) -> Tuple[bool, Optional[Dict[str, Any]]]:
    if not key or not key.strip():
        return False, None

    clean_key = key.strip()

    r = await get_redis_client()
    if r:
        try:
            cached_val = await r.get(f"idemp:{clean_key}")
            if cached_val == "PROCESSING":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A request with this Idempotency-Key is currently being processed. Please retry shortly.",
                )
            if cached_val:
                try:
                    data = json.loads(cached_val)
                    return True, data
                except Exception:
                    pass
        except HTTPException:
            raise
        except Exception as exc:
            logger.debug(f"Redis idempotency lookup failed ({exc}), falling back to database.")

    stmt = select(IdempotencyKey).where(IdempotencyKey.key == clean_key)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    if record:
        if record.response_fingerprint:
            try:
                data = json.loads(record.response_fingerprint)
                return True, data
            except Exception:
                return True, {"status": "completed", "entity_id": record.entity_id}

    if r:
        try:
            await r.set(f"idemp:{clean_key}", "PROCESSING", ex=300)
        except Exception:
            pass

    return False, None


async def save_idempotency_result(
    key: str,
    entity_type: str,
    entity_id: str,
    response_data: Dict[str, Any],
    db: AsyncSession,
) -> None:
    if not key or not key.strip():
        return

    clean_key = key.strip()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=IDEMPOTENCY_DEFAULT_TTL_SECONDS)

    r = await get_redis_client()
    if r:
        try:
            await r.set(
                f"idemp:{clean_key}",
                json.dumps(response_data, default=str),
                ex=IDEMPOTENCY_DEFAULT_TTL_SECONDS,
            )
        except Exception as exc:
            logger.debug(f"Failed to cache idempotency result in Redis: {exc}")

    stmt = select(IdempotencyKey).where(IdempotencyKey.key == clean_key)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.entity_type = entity_type
        existing.entity_id = entity_id
        existing.response_fingerprint = json.dumps(response_data, default=str)
        existing.expires_at = expires_at
    else:
        new_record = IdempotencyKey(
            key=clean_key,
            entity_type=entity_type,
            entity_id=entity_id,
            response_fingerprint=json.dumps(response_data, default=str),
            expires_at=expires_at,
        )
        db.add(new_record)

    await db.flush()


async def clear_idempotency_key(key: str, db: AsyncSession) -> None:
    if not key:
        return
    clean_key = key.strip()
    r = await get_redis_client()
    if r:
        try:
            await r.delete(f"idemp:{clean_key}")
        except Exception:
            pass


store_idempotency = save_idempotency_result
