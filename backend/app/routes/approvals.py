from fastapi import APIRouter, Depends, HTTPException, status, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.ticket import Ticket
from app.models.tool import ToolAction
from app.models.approval import Approval
from app.services.audit_service import log_audit
from app.services.action_service import execute_action
from app.services import idempotency_service
from app.schemas.approval import ApprovalRequest, ApprovalResponse

router = APIRouter()


@router.post('/{action_id}', response_model=ApprovalResponse, status_code=status.HTTP_200_OK)
async def approve_or_reject_action(
    action_id: str,
    req: ApprovalRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(['senior_agent', 'admin'])),
):
    if idempotency_key:
        is_replay, cached = await idempotency_service.check_idempotency(idempotency_key, "approval", db)
        if is_replay and cached:
            response.headers["Idempotent-Replay"] = "true"
            return ApprovalResponse(**cached)

    result = await db.execute(
        select(ToolAction).where(ToolAction.id == action_id).with_for_update()
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail='Action not found')

    existing = await db.execute(select(Approval).where(Approval.action_id == action_id))
    existing_approval = existing.scalar_one_or_none()
    if existing_approval:
        response.headers["Idempotent-Replay"] = "true"
        resp_data = {
            "id": existing_approval.id,
            "action_id": existing_approval.action_id,
            "approver_id": existing_approval.approver_id,
            "decision": existing_approval.decision,
            "reason": existing_approval.reason,
            "decided_at": existing_approval.decided_at,
        }
        if idempotency_key:
            await idempotency_service.save_idempotency_result(
                idempotency_key, "approval", existing_approval.id, resp_data, db
            )
        return ApprovalResponse(**resp_data)

    if action.status != 'pending_approval':
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Action is in state {action.status}, not pending_approval',
        )

    ticket = await db.get(Ticket, action.ticket_id)
    if ticket and ticket.status in ["resolved", "closed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve actions for a resolved or closed ticket.",
        )

    if action.proposed_by_id and action.proposed_by_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maker-Checker policy violation: You cannot approve an action you proposed. A separate reviewer is required.",
        )

    now = datetime.now(timezone.utc)

    approval = Approval(
        id=str(uuid.uuid4()),
        action_id=action_id,
        approver_id=current_user.id,
        decision=req.decision,
        reason=req.reason,
        decided_at=now,
    )
    db.add(approval)

    if req.decision == 'approved':
        action.status = 'approved'
        await execute_action(action, db)
    else:
        action.status = 'rejected'

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action=f'action_{req.decision}',
        resource_type='tool_action',
        resource_id=action_id,
        outcome=req.decision,
        risk_level=action.risk_level,
    )
    await db.flush()

    resp_data = {
        "id": approval.id,
        "action_id": approval.action_id,
        "approver_id": approval.approver_id,
        "decision": approval.decision,
        "reason": approval.reason,
        "decided_at": approval.decided_at,
    }

    if idempotency_key:
        await idempotency_service.save_idempotency_result(
            idempotency_key, "approval", approval.id, resp_data, db
        )

    return ApprovalResponse(**resp_data)
