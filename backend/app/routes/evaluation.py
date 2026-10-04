import uuid
import asyncio
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.eval import EvalRun, EvalResult
from app.schemas.eval import EvalRunResponse, EvalRunDetailResponse, EvalResultResponse
from arq import create_pool
from app.workers.settings import WorkerSettings
from app.workers.tasks import eval_task

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post('/run', status_code=status.HTTP_202_ACCEPTED)
async def start_eval_run(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['admin'])),
):
    eval_run = EvalRun(
        id=str(uuid.uuid4()),
        status='pending',
        created_at=datetime.now(timezone.utc),
    )
    db.add(eval_run)
    await db.commit()

    enqueued = False
    try:
        pool = await create_pool(WorkerSettings.redis_settings)
        await pool.enqueue_job('eval_task', eval_run_id=eval_run.id)
        enqueued = True
    except Exception as exc:
        logger.warning(f"ARQ queue unavailable for eval_task ({exc}), falling back to in-process task")

    if not enqueued:
        asyncio.create_task(eval_task(None, eval_run_id=eval_run.id))

    return {'run_id': eval_run.id}


@router.get('/run/{eval_run_id}', response_model=EvalRunDetailResponse)
async def get_eval_run(
    eval_run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['admin'])),
):
    result = await db.execute(
        select(EvalRun)
        .where(EvalRun.id == eval_run_id)
        .options(selectinload(EvalRun.results))
    )
    eval_run = result.scalar_one_or_none()
    if not eval_run:
        raise HTTPException(status_code=404, detail='Evaluation run not found')

    return EvalRunDetailResponse(
        id=eval_run.id,
        status=eval_run.status,
        summary_metrics=eval_run.summary_metrics,
        created_at=eval_run.created_at,
        results=[
            EvalResultResponse(
                id=r.id,
                eval_run_id=r.eval_run_id,
                case_id=r.case_id,
                expected=r.expected,
                observed=r.observed,
                triage_pass=r.triage_pass,
                citation_pass=r.citation_pass,
                unsafe_block_pass=r.unsafe_block_pass,
                escalation_pass=r.escalation_pass,
            )
            for r in eval_run.results
        ],
    )
