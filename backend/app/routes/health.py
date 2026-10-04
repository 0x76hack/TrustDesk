import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as redis
from app.database import get_db
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get('/health')
async def health_check(db: AsyncSession = Depends(get_db)):
    status_db = False
    status_redis = False

    try:
        await db.execute(text('SELECT 1'))
        status_db = True
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")

    r = None
    try:
        r = redis.from_url(settings.REDIS_URL)
        await r.ping()
        status_redis = True
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
    finally:
        if r is not None:
            try:
                await r.aclose()
            except Exception:
                pass

    return {
        'status': 'healthy' if status_db and status_redis else 'degraded',
        'checks': {
            'database': status_db,
            'redis': status_redis,
        },
    }
