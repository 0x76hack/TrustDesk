import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tool import ToolDefinition, ToolAction
from app.models.approval import Approval
from app.models.ticket import Ticket
from app.models.order import Order
from app.models.message import Message
from app.models.user import User
from app.services.audit_service import log_audit


async def recommend_action(
    ticket: Ticket,
    triage_result: Dict[str, Any],
    risk_result: Dict[str, Any],
    db: AsyncSession,
    run_id: Optional[str] = None,
    proposed_by_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[ToolAction]:
    if ticket.status in ["resolved", "closed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot propose or recommend actions for a resolved or closed ticket.",
        )

    category = triage_result.get("category", "general")
    if not tool_name:
        if category == "refund":
            tool_name = "start_refund_review"
        elif category == "warranty":
            tool_name = "create_replacement_order"
        elif category == "shipping":
            tool_name = "track_shipment"
        elif category == "billing":
            tool_name = "verify_charge"

    if not tool_name:
        return None

    idempotency_key = f"action_{ticket.id}_{tool_name}"
    existing_res = await db.execute(select(ToolAction).where(ToolAction.idempotency_key == idempotency_key))
    existing_action = existing_res.scalar_one_or_none()
    if existing_action:
        return existing_action

    if tool_name in ["start_refund_review", "issue_refund"] and ticket.order_id:
        order = await db.get(Order, ticket.order_id)
        if order and order.total:
            stmt_prev = (
                select(ToolAction)
                .join(Ticket, ToolAction.ticket_id == Ticket.id)
                .where(
                    Ticket.order_id == ticket.order_id,
                    ToolAction.status.in_(["executed", "pending_approval", "approved"]),
                )
            )
            prev_res = await db.execute(stmt_prev)
            prev_actions = prev_res.scalars().all()
            total_prior_refunds = 0.0
            for pa in prev_actions:
                if "refund" in (pa.payload or {}).get("category", "") or "refund" in pa.idempotency_key:
                    total_prior_refunds += float((pa.payload or {}).get("amount", order.total))

            if total_prior_refunds >= order.total:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cumulative refund limit exceeded: order total is ₹{order.total:.2f}, prior refunds total ₹{total_prior_refunds:.2f}.",
                )

    sensitive_tools = {"start_refund_review", "create_replacement_order", "issue_refund", "cancel_order"}
    is_sensitive = tool_name in sensitive_tools

    result = await db.execute(select(ToolDefinition).where(ToolDefinition.name == tool_name))
    tool_def = result.scalar_one_or_none()
    if not tool_def:
        tool_def = ToolDefinition(
            id=str(uuid.uuid4()),
            name=tool_name,
            description=f"Automated tool for {tool_name}",
            category=category,
            is_sensitive=is_sensitive,
            is_read_only=not is_sensitive,
        )
        db.add(tool_def)
        await db.flush()
    else:
        if is_sensitive and not tool_def.is_sensitive:
            tool_def.is_sensitive = True
            tool_def.is_read_only = False

    risk_level = risk_result.get("risk_level", "low")
    action_status = "pending_approval" if (is_sensitive or tool_def.is_sensitive or risk_level in ["high", "critical"]) else "executed"

    action_payload = {"category": category, "subject": ticket.subject or ""}
    if payload and isinstance(payload, dict):
        action_payload.update(payload)

    action_id = str(uuid.uuid4())
    action = ToolAction(
        id=action_id,
        ticket_id=ticket.id,
        run_id=run_id,
        tool_id=tool_def.id,
        payload=action_payload,
        risk_level=risk_level,
        status=action_status,
        idempotency_key=idempotency_key,
        proposed_by_id=proposed_by_id,
        executed_at=datetime.now(timezone.utc) if action_status == "executed" else None,
    )
    db.add(action)
    await db.flush()
    return action


async def execute_action(action: ToolAction, db: AsyncSession) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    tool = None
    if action.tool_id:
        tool_res = await db.execute(select(ToolDefinition).where(ToolDefinition.id == action.tool_id))
        tool = tool_res.scalar_one_or_none()

    tool_name = tool.name if tool else "unknown_tool"
    payload = action.payload or {}

    sensitive_tools = {"start_refund_review", "create_replacement_order", "issue_refund", "cancel_order"}
    is_sensitive = (tool and tool.is_sensitive) or tool_name in sensitive_tools

    if is_sensitive:
        if action.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sensitive action '{tool_name}' requires supervisor approval before execution.",
            )

        # Status alone is mutable; require a persisted positive decision.
        approval_res = await db.execute(
            select(Approval).where(
                Approval.action_id == action.id,
                Approval.decision == "approved",
            )
        )
        approval = approval_res.scalar_one_or_none()
        if approval is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sensitive action '{tool_name}' has no recorded approval decision.",
            )
        if action.proposed_by_id and approval.approver_id == action.proposed_by_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Maker-checker policy violation: proposer cannot approve their own sensitive action.",
            )

    if tool_name in ["issue_refund", "start_refund_review"]:
        from app.services.refund_service import issue_refund_coupon
        ticket = await db.get(Ticket, action.ticket_id)
        amount_raw = payload.get("amount")
        amount = 0.0
        try:
            if amount_raw is not None:
                amount = float(amount_raw)
        except (ValueError, TypeError):
            amount = 0.0

        if amount <= 0 and ticket and ticket.order_id:
            order = await db.get(Order, ticket.order_id)
            if order and order.total:
                amount = float(order.total)
        if amount <= 0:
            amount = 50.0

        refund_res, _ = await issue_refund_coupon(
            ticket_id=action.ticket_id,
            amount=amount,
            db=db,
            idempotency_key=action.idempotency_key,
            actor_id=action.proposed_by_id,
            reason=payload.get("reason"),
            action_id=action.id,
        )
        if isinstance(action.payload, dict):
            action.payload["coupon_code"] = refund_res.get("coupon_code")


    elif tool_name == "cancel_order":
        ticket = await db.get(Ticket, action.ticket_id)
        if ticket and ticket.order_id:
            order = await db.get(Order, ticket.order_id)
            if order:
                order.status = "cancelled"
        sys_msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=action.ticket_id,
            sender_type="system",
            content="Order cancellation confirmed.",
            created_at=now,
        )
        db.add(sys_msg)

    elif tool_name == "track_shipment":
        sys_msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=action.ticket_id,
            sender_type="system",
            content="Courier tracking status refreshed (In Transit).",
            created_at=now,
        )
        db.add(sys_msg)

    action.status = "executed"
    action.executed_at = now
    await db.flush()
    return {"status": "executed", "tool": tool_name, "executed_at": now.isoformat()}


async def approve_action(
    action_id: str,
    approver_user: User,
    decision: str,
    reason: Optional[str],
    db: AsyncSession,
) -> Optional[Approval]:
    if getattr(approver_user, "role", "") not in ["senior_agent", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users with 'senior_agent' or 'admin' role can decide actions",
        )

    result = await db.execute(
        select(ToolAction).where(ToolAction.id == action_id).with_for_update()
    )
    action = result.scalar_one_or_none()
    if not action:
        return None

    if action.status in ["executed", "rejected"]:
        existing = await db.execute(select(Approval).where(Approval.action_id == action_id))
        return existing.scalar_one_or_none()

    if action.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Action is in state '{action.status}', not 'pending_approval'.",
        )

    ticket = await db.get(Ticket, action.ticket_id)
    if ticket and ticket.status in ["resolved", "closed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve actions for a resolved or closed ticket.",
        )

    if action.proposed_by_id and action.proposed_by_id == approver_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maker-Checker policy violation: The operative who proposed this action cannot approve it. A separate reviewer is required.",
        )

    now = datetime.now(timezone.utc)
    approval = Approval(
        id=str(uuid.uuid4()),
        action_id=action_id,
        approver_id=approver_user.id,
        decision=decision,
        reason=reason,
        decided_at=now,
    )
    db.add(approval)

    if decision == "approved":
        action.status = "approved"
        await execute_action(action, db)
    else:
        action.status = "rejected"

    await log_audit(
        db=db,
        actor_id=approver_user.id,
        action=f"action_{decision}",
        resource_type="tool_action",
        resource_id=action_id,
        outcome=decision,
        risk_level=action.risk_level,
    )
    await db.flush()
    return approval
