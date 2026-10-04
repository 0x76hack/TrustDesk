import uuid
import secrets
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.coupon import Coupon
from app.models.ticket import Ticket
from app.models.order import Order
from app.models.message import Message
from app.services.audit_service import log_audit

_coupon_locks: Dict[str, asyncio.Lock] = {}


def _get_coupon_lock(code: str) -> asyncio.Lock:
    if code not in _coupon_locks:
        _coupon_locks[code] = asyncio.Lock()
    return _coupon_locks[code]


def generate_coupon_code() -> str:
    suffix = secrets.token_hex(4).upper()
    return f"SWIGGY-REF-{suffix}"


async def create_coupon(
    customer_id: str,
    amount: float,
    original_order_id: Optional[str],
    ticket_id: Optional[str],
    idempotency_key: Optional[str],
    db: AsyncSession,
    currency: str = "INR",
    expires_days: int = 90,
) -> Coupon:
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Coupon amount must be greater than zero.",
        )

    if idempotency_key:
        stmt = select(Coupon).where(Coupon.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

    now = datetime.now(timezone.utc)
    coupon = Coupon(
        id=str(uuid.uuid4()),
        code=generate_coupon_code(),
        customer_id=customer_id,
        original_order_id=original_order_id,
        ticket_id=ticket_id,
        amount=round(amount, 2),
        currency=currency,
        status="active",
        idempotency_key=idempotency_key,
        expires_at=now + timedelta(days=expires_days),
        created_at=now,
    )
    db.add(coupon)
    await db.flush()
    return coupon


async def redeem_coupon(
    coupon_code: str,
    customer_id: str,
    order_id: str,
    db: AsyncSession,
    ticket_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Tuple[Coupon, bool]:
    clean_code = coupon_code.strip().upper()
    async with _get_coupon_lock(clean_code):
        stmt = select(Coupon).where(Coupon.code == clean_code).with_for_update()
        res = await db.execute(stmt)
        coupon = res.scalar_one_or_none()

        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Coupon '{clean_code}' not found.",
            )

        if coupon.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="COUPON_ACCOUNT_MISMATCH: This coupon belongs to a different customer account.",
            )

        now = datetime.now(timezone.utc)
        if coupon.expires_at and coupon.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Coupon '{clean_code}' has expired on {coupon.expires_at.isoformat()}.",
            )

        if coupon.status == "redeemed":
            if coupon.redeemed_order_id == order_id:
                return coupon, True
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "COUPON_ALREADY_REDEEMED",
                    "message": f"Coupon '{clean_code}' was already redeemed on Order '{coupon.redeemed_order_id}'. Duplicate redemption across multiple orders is prohibited.",
                    "redeemed_order_id": coupon.redeemed_order_id,
                    "redeemed_at": coupon.redeemed_at.isoformat() if coupon.redeemed_at else None,
                },
            )

        coupon.status = "redeemed"
        coupon.redeemed_order_id = order_id
        coupon.redeemed_ticket_id = ticket_id
        coupon.redeemed_at = now

        order = await db.get(Order, order_id)
        if order:
            order.coupon_code = coupon.code
            order.discount_amount = coupon.amount

        if idempotency_key:
            from app.services.idempotency_service import store_idempotency
            await store_idempotency(
                key=idempotency_key,
                entity_type="coupon_redemption",
                entity_id=clean_code,
                response_data={
                    "coupon_code": clean_code,
                    "order_id": order_id,
                    "discount_amount": coupon.amount,
                    "status": "redeemed",
                },
                db=db,
            )

        await db.commit()
        await db.refresh(coupon)
        return coupon, False


async def process_ticket_coupon_intake(
    ticket: Ticket,
    coupon_code: str,
    customer_id: str,
    order_id: Optional[str],
    db: AsyncSession,
) -> Dict[str, Any]:
    clean_code = coupon_code.strip().upper()
    now = datetime.now(timezone.utc)

    async with _get_coupon_lock(clean_code):
        stmt = select(Coupon).where(Coupon.code == clean_code).with_for_update()
        res = await db.execute(stmt)
        coupon = res.scalar_one_or_none()

        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Referenced coupon '{clean_code}' not found.",
            )

        if coupon.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="COUPON_ACCOUNT_MISMATCH: This coupon is issued to another customer account.",
            )

        if coupon.status == "redeemed":
            if order_id and coupon.redeemed_order_id == order_id:
                ticket.coupon_code = coupon.code
                ticket.coupon_discount = coupon.amount
                ticket.coupon_status = "verified"
                ticket.coupon_abuse_flag = False
                sys_msg = Message(
                    id=str(uuid.uuid4()),
                    ticket_id=ticket.id,
                    sender_type="system",
                    content=f"[COUPON USAGE VERIFIED] Customer applied refund voucher {coupon.code} (-Rs. {coupon.amount:.2f}) to Order {order_id}.",
                    created_at=now,
                )
                db.add(sys_msg)
                await db.commit()
                return {"status": "verified", "coupon": coupon}

            ticket.status = "resolved"
            ticket.close_reason = "duplicate_coupon_rejected"
            ticket.coupon_code = coupon.code
            ticket.coupon_discount = 0.0
            ticket.coupon_status = "duplicate_rejected"
            ticket.coupon_abuse_flag = True
            ticket.escalation_flag = True
            ticket.risk_level = "critical"
            ticket.category = "account_security"
            ticket.resolved_at = now

            sys_msg = Message(
                id=str(uuid.uuid4()),
                ticket_id=ticket.id,
                sender_type="system",
                content=f"[SECURITY ALERT: DUPLICATE COUPON REDEMPTION ATTEMPT] Coupon '{coupon.code}' was already redeemed on Order '{coupon.redeemed_order_id}'. Ticket auto-closed as duplicate (409 Conflict).",
                created_at=now,
            )
            db.add(sys_msg)

            await log_audit(
                db=db,
                actor_id=customer_id,
                action="duplicate_coupon_auto_closed",
                resource_type="ticket",
                resource_id=ticket.id,
                outcome="conflict_409",
                risk_level="critical",
                guardrail_result={
                    "coupon_code": coupon.code,
                    "prior_order_id": coupon.redeemed_order_id,
                    "attempted_order_id": order_id,
                },
            )
            await db.commit()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "COUPON_ALREADY_REDEEMED",
                    "ticket_id": ticket.id,
                    "status": "auto_closed",
                    "message": f"Coupon '{coupon.code}' was already redeemed on Order '{coupon.redeemed_order_id}'. Ticket auto-closed as duplicate.",
                    "redeemed_order_id": coupon.redeemed_order_id,
                },
            )

        if order_id:
            coupon.status = "redeemed"
            coupon.redeemed_order_id = order_id
            coupon.redeemed_ticket_id = ticket.id
            coupon.redeemed_at = now

            order = await db.get(Order, order_id)
            if order:
                order.coupon_code = coupon.code
                order.discount_amount = coupon.amount

        ticket.coupon_code = coupon.code
        ticket.coupon_discount = coupon.amount
        ticket.coupon_status = "redeemed"
        ticket.coupon_abuse_flag = False

        sys_msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            sender_type="system",
            content=f"[COUPON USAGE VERIFIED] Refund coupon {coupon.code} (-Rs. {coupon.amount:.2f}) redeemed and applied to Order {order_id}.",
            created_at=now,
        )
        db.add(sys_msg)
        await db.commit()
        return {"status": "redeemed", "coupon": coupon}


async def list_customer_coupons(customer_id: str, db: AsyncSession) -> List[Coupon]:
    stmt = (
        select(Coupon)
        .where(Coupon.customer_id == customer_id)
        .order_by(Coupon.created_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())
