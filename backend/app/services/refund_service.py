import uuid
import secrets
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.ticket import Ticket
from app.models.order import Order
from app.models.message import Message
from app.models.tool import ToolAction, ToolDefinition
from app.models.coupon import Coupon
from app.services.audit_service import log_audit
from app.services.idempotency_service import check_idempotency, store_idempotency
from app.services.coupon_service import create_coupon, generate_coupon_code

_refund_locks: Dict[str, asyncio.Lock] = {}


def _get_refund_lock(key: str) -> asyncio.Lock:
    if key not in _refund_locks:
        _refund_locks[key] = asyncio.Lock()
    return _refund_locks[key]


async def issue_refund_coupon(
    ticket_id: str,
    amount: float,
    db: AsyncSession,
    idempotency_key: Optional[str] = None,
    actor_id: Optional[str] = None,
    reason: Optional[str] = None,
    action_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    async with _get_refund_lock(ticket_id):
        if amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Refund amount must be positive.",
            )

        if idempotency_key:
            is_replay, cached = await check_idempotency(idempotency_key, "refund", db)
            if is_replay and cached:
                return cached, True

        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket '{ticket_id}' not found.",
            )

        if ticket.coupon_code:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"REFUND_COUPON_ALREADY_ISSUED: A refund coupon ({ticket.coupon_code}) has already been issued for Ticket #{ticket.id[:8]}.",
            )

        existing_ticket_cp_res = await db.execute(
            select(Coupon).where(Coupon.ticket_id == ticket.id)
        )
        existing_ticket_cp = existing_ticket_cp_res.scalar_one_or_none()
        if isinstance(existing_ticket_cp, Coupon):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"REFUND_COUPON_ALREADY_ISSUED: A refund coupon ({existing_ticket_cp.code}) has already been issued for Ticket #{ticket.id[:8]}.",
            )

        order: Optional[Order] = None
        if ticket.order_id:
            existing_order_cp_res = await db.execute(
                select(Coupon).where(Coupon.original_order_id == ticket.order_id)
            )
            existing_order_cp = existing_order_cp_res.scalar_one_or_none()
            if isinstance(existing_order_cp, Coupon):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"REFUND_COUPON_ALREADY_ISSUED: A refund coupon ({existing_order_cp.code}) has already been issued for Order #{ticket.order_id[:8]}.",
                )

            order = await db.get(Order, ticket.order_id)
            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Linked order '{ticket.order_id}' not found.",
                )

        if order and order.total is not None:
            order_total = float(order.total)
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
            prior_refunds = 0.0
            for pa in prev_actions:
                if action_id and pa.id == action_id:
                    continue
                payload = pa.payload or {}
                is_refund_action = (
                    "refund" in str(payload.get("category", "")).lower()
                    or "refund" in str(pa.idempotency_key or "").lower()
                    or "coupon_code" in payload
                )
                if is_refund_action:
                    raw_amt = payload.get("amount")
                    try:
                        prior_refunds += float(raw_amt) if raw_amt is not None else order_total
                    except (ValueError, TypeError):
                        prior_refunds += order_total

            if round(prior_refunds + amount, 2) > round(order_total, 2):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cumulative refund limit exceeded: order total is ₹{order_total:.2f}, prior refunds total ₹{prior_refunds:.2f}, requested ₹{amount:.2f}.",
                )

        coupon_obj = await create_coupon(
            customer_id=ticket.customer_id,
            amount=amount,
            original_order_id=ticket.order_id,
            ticket_id=ticket.id,
            idempotency_key=idempotency_key,
            db=db,
        )
        coupon_code = coupon_obj.code
        now = datetime.now(timezone.utc)

        msg_content = (
            f"[REFUND COUPON ISSUED]\n"
            f"Coupon Code: {coupon_code}\n"
            f"Value: ₹{amount:.2f}\n"
            f"Valid for 90 days across all restaurants on Swiggy."
        )
        system_msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            sender_type="system",
            content=msg_content,
            created_at=now,
        )
        db.add(system_msg)

        ticket.coupon_code = coupon_code
        ticket.coupon_discount = amount
        ticket.coupon_status = "issued"

        if order:
            order.status = "refunded"

        tool_def_res = await db.execute(select(ToolDefinition).where(ToolDefinition.name == "issue_refund"))
        tool_def = tool_def_res.scalar_one_or_none()
        if not tool_def:
            tool_def = ToolDefinition(
                id=str(uuid.uuid4()),
                name="issue_refund",
                description="Automated tool for issuing refund coupon",
                category="refund",
                is_sensitive=True,
                is_read_only=False,
            )
            db.add(tool_def)
            await db.flush()

        if action_id:
            existing_action = await db.get(ToolAction, action_id)
            if existing_action:
                existing_action.status = "executed"
                existing_action.executed_at = now
                if not isinstance(existing_action.payload, dict):
                    existing_action.payload = {}
                existing_action.payload["coupon_code"] = coupon_code
                existing_action.payload["amount"] = amount
                existing_action.payload["category"] = "refund"
        else:
            new_action = ToolAction(
                id=str(uuid.uuid4()),
                ticket_id=ticket.id,
                tool_id=tool_def.id,
                payload={"category": "refund", "amount": amount, "coupon_code": coupon_code, "reason": reason},
                risk_level="low",
                status="executed",
                idempotency_key=idempotency_key or f"refund_{ticket.id}_{coupon_code}",
                proposed_by_id=actor_id,
                executed_at=now,
            )
            db.add(new_action)

        await log_audit(
            db=db,
            actor_id=actor_id,
            action="issue_refund_coupon",
            resource_type="ticket",
            resource_id=ticket.id,
            outcome="success",
            guardrail_result={"coupon_code": coupon_code, "amount": amount},
        )

        response_data: Dict[str, Any] = {
            "coupon_code": coupon_code,
            "amount": amount,
            "ticket_id": ticket.id,
            "order_id": ticket.order_id,
            "status": "issued",
            "message": f"Refund coupon {coupon_code} issued successfully.",
        }

        if idempotency_key:
            await store_idempotency(
                key=idempotency_key,
                entity_type="refund",
                entity_id=coupon_code,
                response_data=response_data,
                db=db,
            )

        await db.commit()
        return response_data, False
