from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.run import Run
from app.schemas.run import RunResponse

router = APIRouter()


@router.get('/{run_id}', response_model=RunResponse)
async def get_run_status(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['agent', 'senior_agent', 'admin'])),
):
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail='Run not found')
    return RunResponse(
        id=run.id,
        ticket_id=run.ticket_id,
        run_type=run.run_type,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        error=run.error,
    )
