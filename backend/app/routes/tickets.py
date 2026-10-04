import uuid
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import require_role
from app.models.user import User
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.customer import Customer
from app.models.order import Order
from app.models.draft import Draft
from app.models.tool import ToolAction
from app.models.approval import Approval
from app.models.run import Run
from app.models.audit_log import AuditLog
from app.models.note import TicketNote
from app.services.audit_service import log_audit
from app.services import idempotency_service, coupon_service
from app.routes.customer_portal import validate_web_security_probe
from app.constants import (
    TicketStatus,
    TicketPriority,
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    DRAFT_POLL_ATTEMPTS,
    DRAFT_POLL_INTERVAL_S,
)
from app.schemas.ticket import (
    TicketCreate,
    TicketResponse,
    TicketDetailResponse,
    MessageCreate,
    MessageResponse,
    TicketUpdateRequest,
    TicketEscalateRequest,
    TicketCloseRequest,
    TicketAssignRequest,
    InternalNoteCreate,
    InternalNoteResponse,
    TimelineEventResponse,
    RunTriggerResponse,
    RefundRequest,
    RefundResponse,
)
from app.schemas.draft import DraftDetailResponse
from app.schemas.action import ActionRequest, ActionDetailResponse
from app.schemas.auth import UserResponse

from arq import create_pool
from app.workers.settings import WorkerSettings
from app.services import guardrail_service
from app.workers.tasks import triage_task, draft_task, action_task

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


def run_tracked_task(coro):
    task = asyncio.create_task(coro)
    _background_tasks.add(task)

    def _done_callback(t: asyncio.Task):
        _background_tasks.discard(t)
        if not t.cancelled() and t.exception():
            logger.error(f"In-process background worker task failed: {t.exception()}", exc_info=t.exception())

    task.add_done_callback(_done_callback)
    return task


router = APIRouter()


async def get_ticket_or_404(ticket_id: str, db: AsyncSession) -> Ticket:
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def create_system_message(ticket_id: str, content: str) -> Message:
    return Message(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender_type="system",
        content=content,
    )


@router.get("/", response_model=List[TicketResponse])
async def list_tickets(
    limit: int = Query(DEFAULT_PAGE_LIMIT, ge=1, le=MAX_PAGE_LIMIT),
    offset: int = Query(0, ge=0),
    cursor: Optional[str] = Query(None, description="ISO timestamp cursor for pagination"),
    queue: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.assignee))
        .order_by(Ticket.created_at.desc())
        .limit(limit)
    )

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(Ticket.created_at < cursor_dt)
        except ValueError:
            pass
    else:
        stmt = stmt.offset(offset)

    if queue == "open":
        stmt = stmt.where((Ticket.status == "open") | ((Ticket.status == "working") & (Ticket.assigned_to.is_(None))))
    elif queue == "working":
        stmt = stmt.where(Ticket.status == "working", Ticket.assigned_to.isnot(None))
    elif queue == "escalated":
        stmt = stmt.where(Ticket.status == "escalated")
    elif queue == "resolved":
        stmt = stmt.where(Ticket.status == "resolved")

    if category:
        stmt = stmt.where(Ticket.category == category)

    result = await db.execute(stmt)
    tickets = result.scalars().all()
    
    for ticket in tickets:
        ticket.assignee_name = ticket.computed_assignee_name
    return tickets


@router.post("/", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    req: TicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    cust_check = await db.execute(select(Customer).where(Customer.id == req.customer_id))
    customer = cust_check.scalar_one_or_none()
    if not customer:
        customer = Customer(
            id=req.customer_id,
            name=f"Customer #{req.customer_id[:8]}",
            email=f"{req.customer_id[:8]}@customer.example.com",
        )
        db.add(customer)
        await db.flush()

    valid_order_id = None
    if req.order_id:
        ord_check = await db.execute(select(Order).where(Order.id == req.order_id))
        order_obj = ord_check.scalar_one_or_none()
        if not order_obj and not validate_web_security_probe(req.order_id):
            order_obj = Order(
                id=req.order_id,
                customer_id=customer.id,
                restaurant="Express Cloud Kitchen",
                status="delivered",
                total=450.0,
                currency="INR",
            )
            db.add(order_obj)
            await db.flush()
        if order_obj:
            valid_order_id = order_obj.id

    msg_body = getattr(req, "message", None) or getattr(req, "initial_message", None)
    for field_name, value in [("order_id", req.order_id), ("subject", req.subject), ("message", msg_body)]:
        if value:
            threat = validate_web_security_probe(value)
            if threat:
                ticket_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc)
                attack_ticket = Ticket(
                    id=ticket_id,
                    customer_id=customer.id,
                    order_id=valid_order_id,
                    subject=req.subject,
                    category="account_security",
                    priority="urgent",
                    status="resolved",
                    close_reason=f"security_attack_blocked: {threat}",
                    risk_level="critical",
                    escalation_flag=True,
                    created_at=now,
                    updated_at=now,
                    resolved_at=now,
                )
                db.add(attack_ticket)

                if msg_body:
                    cust_msg = Message(
                        id=str(uuid.uuid4()),
                        ticket_id=ticket_id,
                        sender_type="customer",
                        content=str(msg_body),
                        created_at=now,
                    )
                    db.add(cust_msg)

                sys_msg = Message(
                    id=str(uuid.uuid4()),
                    ticket_id=ticket_id,
                    sender_type="system",
                    content=f"[SECURITY ALERT: WEB EXPLOIT ATTACK DETECTED - AUTO-CLOSED] Threat detected: {threat}. Payload neutralized and request rejected. Ticket auto-closed immediately.",
                    created_at=now,
                )
                db.add(sys_msg)

                await log_audit(
                    db=db,
                    actor_id=customer.id,
                    action="security_attack_auto_closed",
                    resource_type="ticket",
                    resource_id=ticket_id,
                    outcome="rejected_400",
                    risk_level="critical",
                    guardrail_result={"threat": threat, "field": field_name},
                )
                await db.commit()

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "SECURITY_ATTACK_BLOCKED",
                        "ticket_id": ticket_id,
                        "threat_type": threat,
                        "status": "auto_closed",
                        "message": f"Security attack blocked: {threat}. The ticket has been auto-closed and flagged for security review.",
                    },
                )

    ticket_id = str(uuid.uuid4())
    ticket = Ticket(
        id=ticket_id,
        customer_id=customer.id,
        order_id=valid_order_id,
        subject=req.subject,
        category=getattr(req, "category", None) or "general",
        priority=getattr(req, "priority", None) or "medium",
        status=TicketStatus.OPEN.value,
        escalation_flag=False,
    )
    db.add(ticket)
    await db.flush()

    if getattr(req, "coupon_code", None):
        await coupon_service.process_ticket_coupon_intake(
            ticket=ticket,
            coupon_code=req.coupon_code,
            customer_id=customer.id,
            order_id=valid_order_id,
            db=db,
        )
    elif valid_order_id:
        order_res = await db.get(Order, valid_order_id)
        if order_res and order_res.coupon_code:
            ticket.coupon_code = order_res.coupon_code
            ticket.coupon_discount = order_res.discount_amount

    raw_msg = getattr(req, "message", None) or getattr(req, "initial_message", None)
    if raw_msg:
        from app.services import guardrail_service
        fence_res = guardrail_service.fence_input(raw_msg)
        if not fence_res.get("is_safe", True):
            ticket.status = TicketStatus.ESCALATED.value
            ticket.escalation_flag = True
            ticket.risk_level = "critical"
            await log_audit(
                db=db,
                actor_id=customer.id,
                action="security_gate_blocked",
                resource_type="ticket",
                resource_id=ticket_id,
                outcome="escalated_to_senior_queue",
                risk_level="critical",
                guardrail_result=fence_res,
            )

        msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            sender_type="customer",
            content=raw_msg,
        )
        db.add(msg)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="ticket_created",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome="created",
    )

    sys_msg = Message(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender_type="system",
        content=f"Ticket intake registered by {current_user.name or current_user.username}. Queue: Open.",
    )
    db.add(sys_msg)

    await db.commit()
    await db.refresh(ticket)
    return TicketResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        order_id=ticket.order_id,
        subject=ticket.subject,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        escalation_flag=ticket.escalation_flag,
        risk_level=ticket.risk_level,
        assigned_to=ticket.assigned_to,
        assigned_at=ticket.assigned_at,
        first_response_at=ticket.first_response_at,
        resolved_at=ticket.resolved_at,
        notes=ticket.notes,
        assignee_name=None,
        coupon_code=ticket.coupon_code,
        coupon_discount=ticket.coupon_discount,
        coupon_status=ticket.coupon_status,
        coupon_abuse_flag=ticket.coupon_abuse_flag,
        close_reason=ticket.close_reason,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get("/assigned/me", response_model=List[TicketResponse])
async def list_my_assigned_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.assignee))
        .where(Ticket.assigned_to == current_user.id)
        .order_by(Ticket.updated_at.desc())
    )
    result = await db.execute(stmt)
    tickets = result.scalars().all()
    for ticket in tickets:
        ticket.assignee_name = ticket.computed_assignee_name
    return tickets


@router.get("/my-history", response_model=List[TicketResponse])
async def list_my_history_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.assignee))
        .where(Ticket.assigned_to == current_user.id)
        .order_by(Ticket.updated_at.desc())
    )
    result = await db.execute(stmt)
    tickets = result.scalars().all()
    for ticket in tickets:
        ticket.assignee_name = ticket.computed_assignee_name
    return tickets


@router.get("/agents", response_model=List[UserResponse])
async def list_available_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(User)
        .where(User.role.in_(["agent", "senior_agent", "admin"]))
        .where(User.username != "ai_agent")
        .order_by(User.name.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket_detail(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(
            selectinload(Ticket.customer),
            selectinload(Ticket.order).selectinload(Order.items),
            selectinload(Ticket.messages),
            selectinload(Ticket.assignee),
        )
    )
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TicketDetailResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        order_id=ticket.order_id,
        subject=ticket.subject,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        escalation_flag=ticket.escalation_flag,
        risk_level=ticket.risk_level,
        assigned_to=ticket.assigned_to,
        assigned_at=ticket.assigned_at,
        first_response_at=ticket.first_response_at,
        resolved_at=ticket.resolved_at,
        notes=ticket.notes,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        customer=ticket.customer,
        order=ticket.order,
        messages=ticket.messages,
        assignee_name=ticket.computed_assignee_name,
        coupon_code=ticket.coupon_code,
        coupon_discount=ticket.coupon_discount,
        coupon_status=ticket.coupon_status,
        coupon_abuse_flag=ticket.coupon_abuse_flag,
        close_reason=ticket.close_reason,
    )


@router.post("/{ticket_id}/assign", response_model=TicketResponse)
async def assign_ticket(
    ticket_id: str,
    req: Optional[TicketAssignRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = select(Ticket).where(Ticket.id == ticket_id).with_for_update()
    ticket_res = await db.execute(stmt)
    ticket = ticket_res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket '{ticket_id}' not found")

    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Cannot assign a resolved ticket")

    if ticket.status == "escalated" and current_user.role == "agent":
        raise HTTPException(status_code=403, detail="Senior agents or administrators only can pick escalated tickets")

    target_user_id = req.user_id if (req and req.user_id) else current_user.id
    assignee_user = await db.get(User, target_user_id)
    if not assignee_user:
        raise HTTPException(status_code=404, detail=f"Target assignee '{target_user_id}' not found")

    assignee_name = assignee_user.name or assignee_user.username

    if ticket.assigned_to:
        if ticket.assigned_to == assignee_user.id:
            ticket.assignee_name = assignee_name
            return TicketResponse(
                id=ticket.id,
                customer_id=ticket.customer_id,
                order_id=ticket.order_id,
                subject=ticket.subject,
                category=ticket.category,
                priority=ticket.priority,
                status=ticket.status,
                escalation_flag=ticket.escalation_flag,
                risk_level=ticket.risk_level,
                assigned_to=ticket.assigned_to,
                assigned_at=ticket.assigned_at,
                first_response_at=ticket.first_response_at,
                resolved_at=ticket.resolved_at,
                notes=ticket.notes,
                assignee_name=assignee_name,
                coupon_code=ticket.coupon_code,
                coupon_discount=ticket.coupon_discount,
                coupon_status=ticket.coupon_status,
                coupon_abuse_flag=ticket.coupon_abuse_flag,
                close_reason=ticket.close_reason,
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )
        if current_user.role not in ["admin", "senior_agent"]:
            assigned_user = await db.get(User, ticket.assigned_to)
            locked_name = (assigned_user.name or assigned_user.username) if assigned_user else (ticket.assignee_name or f"Agent #{ticket.assigned_to[:8]}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ticket is already assigned to {locked_name}.",
            )

    ticket.assigned_to = assignee_user.id
    assignee_name = assignee_user.name or assignee_user.username

    ticket.assigned_at = datetime.now(timezone.utc)
    ticket.status = "working"
    ticket.escalation_flag = False
    ticket.updated_at = datetime.now(timezone.utc)
    ticket.assignee_name = assignee_name

    audit_msg = create_system_message(
        ticket_id=ticket_id,
        content=f"Ticket assigned to {assignee_name} ({current_user.role}). Status changed to working.",
    )
    db.add(audit_msg)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="ticket_assigned",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome=f"assigned:{assignee_name}"[:100],
    )

    await db.commit()
    await db.refresh(ticket)
    return TicketResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        order_id=ticket.order_id,
        subject=ticket.subject,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        escalation_flag=ticket.escalation_flag,
        risk_level=ticket.risk_level,
        assigned_to=ticket.assigned_to,
        assigned_at=ticket.assigned_at,
        first_response_at=ticket.first_response_at,
        resolved_at=ticket.resolved_at,
        notes=ticket.notes,
        assignee_name=assignee_name,
        coupon_code=ticket.coupon_code,
        coupon_discount=ticket.coupon_discount,
        coupon_status=ticket.coupon_status,
        coupon_abuse_flag=ticket.coupon_abuse_flag,
        close_reason=ticket.close_reason,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.post("/{ticket_id}/unassign", response_model=TicketResponse)
async def unassign_ticket(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)

    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Cannot unassign a resolved ticket")

    ticket.assigned_to = None
    ticket.assigned_at = None
    ticket.first_response_at = None
    ticket.status = "open"
    ticket.escalation_flag = False
    ticket.updated_at = datetime.now(timezone.utc)

    audit_msg = create_system_message(
        ticket_id=ticket_id,
        content=f"Ticket unassigned by {current_user.name or current_user.username}. Status returned to open.",
    )
    db.add(audit_msg)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="ticket_unassigned",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome="open",
    )

    await db.commit()
    await db.refresh(ticket)
    return TicketResponse(
        id=ticket.id,
        customer_id=ticket.customer_id,
        order_id=ticket.order_id,
        subject=ticket.subject,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        escalation_flag=ticket.escalation_flag,
        risk_level=ticket.risk_level,
        assigned_to=ticket.assigned_to,
        assigned_at=ticket.assigned_at,
        first_response_at=ticket.first_response_at,
        resolved_at=ticket.resolved_at,
        notes=ticket.notes,
        assignee_name=None,
        coupon_code=ticket.coupon_code,
        coupon_discount=ticket.coupon_discount,
        coupon_status=ticket.coupon_status,
        coupon_abuse_flag=ticket.coupon_abuse_flag,
        close_reason=ticket.close_reason,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: str,
    req: TicketUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)

    if req.status is not None and req.status != ticket.status:
        VALID_TRANSITIONS = {
            "open": {"working", "escalated", "resolved"},
            "working": {"escalated", "resolved"},
            "escalated": {"working", "resolved"},
            "resolved": set(),
        }
        allowed = VALID_TRANSITIONS.get(ticket.status, set())
        if req.status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state transition: Cannot change ticket from '{ticket.status}' to '{req.status}'.",
            )
        if req.status == "working" and not ticket.assigned_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set ticket status to 'working' without an assigned agent. Claim or assign the ticket first.",
            )
        ticket.status = req.status
    if req.priority is not None:
        ticket.priority = req.priority
    if req.category is not None:
        ticket.category = req.category
    if req.escalation_flag is not None:
        ticket.escalation_flag = req.escalation_flag

    ticket.updated_at = datetime.now(timezone.utc)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="ticket_update",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome=ticket.status,
    )

    await db.commit()
    await db.refresh(ticket)
    ticket.assignee_name = ticket.computed_assignee_name
    return ticket


@router.post("/{ticket_id}/escalate", response_model=TicketResponse)
async def escalate_ticket(
    ticket_id: str,
    req: TicketEscalateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)

    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Cannot escalate a resolved ticket")
    if ticket.status == "escalated":
        raise HTTPException(status_code=400, detail="Ticket is already escalated")

    ticket.status = "escalated"
    ticket.escalation_flag = True
    ticket.assigned_to = None
    ticket.assigned_at = None
    ticket.updated_at = datetime.now(timezone.utc)

    reason_desc = f"{req.reason}: {req.custom_reason}" if req.custom_reason else req.reason
    note_text = f" [Note: {req.note}]" if req.note else ""

    audit_msg = create_system_message(
        ticket_id=ticket_id,
        content=f"Ticket escalated by {current_user.name or current_user.username} ({current_user.role}) to Senior Queue. Reason: {reason_desc}{note_text}",
    )
    db.add(audit_msg)

    author_user = await db.get(User, current_user.id) if current_user and current_user.id else None
    safe_author_id = current_user.id if author_user else None

    escalation_note_content = f"[ESCALATION REASON] {reason_desc}"
    if req.note and req.note.strip():
        escalation_note_content += f"\n\n[SENIOR REVIEW NOTE]\n{req.note.strip()}"

    note_record = TicketNote(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        author_id=safe_author_id,
        content=escalation_note_content,
    )
    db.add(note_record)

    await log_audit(
        db=db,
        actor_id=safe_author_id,
        action="ticket_escalated",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome="escalated",
    )

    await db.commit()
    await db.refresh(ticket)
    ticket.assignee_name = None
    return ticket


@router.post("/{ticket_id}/close", response_model=TicketResponse)
async def close_ticket(
    ticket_id: str,
    req: TicketCloseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)

    if ticket.status == "resolved":
        raise HTTPException(status_code=400, detail="Ticket is already resolved")

    pending_actions_res = await db.execute(
        select(ToolAction).where(
            ToolAction.ticket_id == ticket_id,
            ToolAction.status == "pending_approval",
        )
    )
    pending_actions = pending_actions_res.scalars().all()
    for act in pending_actions:
        act.status = "rejected"
        appr = Approval(
            id=str(uuid.uuid4()),
            action_id=act.id,
            approver_id=current_user.id,
            decision="rejected",
            reason=f"Action auto-rejected on ticket resolution by {current_user.username}",
            decided_at=datetime.now(timezone.utc),
        )
        db.add(appr)
        await log_audit(
            db=db,
            actor_id=current_user.id,
            action="action_auto_rejected_on_ticket_close",
            resource_type="tool_action",
            resource_id=act.id,
            outcome="rejected",
            risk_level=act.risk_level,
        )

    real_user = await db.get(User, current_user.id)
    safe_author_id = real_user.id if real_user else None

    if not ticket.assigned_to:
        if safe_author_id:
            ticket.assigned_to = safe_author_id
            ticket.assigned_at = ticket.assigned_at or datetime.now(timezone.utc)

    ticket.status = "resolved"
    ticket.resolved_at = datetime.now(timezone.utc)
    ticket.notes = req.notes
    ticket.escalation_flag = False
    ticket.updated_at = datetime.now(timezone.utc)

    assignee_display = (real_user.name or real_user.username) if real_user else (current_user.name or current_user.username)
    ticket.assignee_name = assignee_display

    res_type = f"{req.resolution_type} ({req.custom_resolution})" if req.custom_resolution else (req.resolution_type or "resolved")
    note_msg = create_system_message(
        ticket_id=ticket_id,
        content=f"Ticket closed and resolved by {assignee_display} ({current_user.role}). Resolution: {res_type}. Resolution Notes: {req.notes}",
    )
    db.add(note_msg)

    if req.notes and req.notes.strip():
        close_note_record = TicketNote(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            author_id=safe_author_id or ticket.assigned_to,
            content=f"[RESOLUTION NOTE - {res_type}]\n{req.notes.strip()}",
        )
        db.add(close_note_record)

    await log_audit(
        db=db,
        actor_id=current_user.id,
        action="ticket_closed",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome="resolved",
    )

    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}/messages", response_model=List[MessageResponse])
async def get_ticket_messages(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = select(Message).where(Message.ticket_id == ticket_id).order_by(Message.created_at)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{ticket_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def add_ticket_message(
    ticket_id: str,
    req: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)

    if ticket.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send message. This ticket is resolved and the conversation chat is closed.",
        )

    fence_res = guardrail_service.fence_input(req.content)
    if not fence_res.get("is_safe", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message blocked by safety guardrail: {fence_res.get('details')}",
        )

    if ticket.status == "open":
        ticket.status = "working"
        if not ticket.assigned_to:
            ticket.assigned_to = current_user.id
            ticket.assigned_at = ticket.assigned_at or datetime.now(timezone.utc)

    ticket.first_response_at = ticket.first_response_at or datetime.now(timezone.utc)
    ticket.updated_at = datetime.now(timezone.utc)

    msg = Message(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender_type=req.sender_type or "agent",
        content=req.content,
    )
    db.add(msg)

    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/{ticket_id}/triage", response_model=RunTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_triage(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    await get_ticket_or_404(ticket_id, db)

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        ticket_id=ticket_id,
        run_type="triage",
        status="pending",
    )
    db.add(run)
    await db.commit()

    enqueued = False
    try:
        pool = await create_pool(WorkerSettings.redis_settings)
        await pool.enqueue_job("triage_task", run_id=run.id, ticket_id=ticket_id)
        enqueued = True
    except Exception as exc:
        logger.warning(f"ARQ queue unavailable for triage_task ({exc}), falling back to in-process task")

    if not enqueued:
        run_tracked_task(triage_task(None, run_id=run.id, ticket_id=ticket_id))

    return RunTriggerResponse(run_id=run_id)


@router.post("/{ticket_id}/draft", response_model=RunTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_draft(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    await get_ticket_or_404(ticket_id, db)

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        ticket_id=ticket_id,
        run_type="draft",
        status="pending",
    )
    db.add(run)
    await db.commit()

    enqueued = False
    try:
        pool = await create_pool(WorkerSettings.redis_settings)
        await pool.enqueue_job("draft_task", run_id=run.id, ticket_id=ticket_id)
        enqueued = True
    except Exception as exc:
        logger.warning(f"ARQ queue unavailable for draft_task ({exc}), falling back to in-process task")

    if not enqueued:
        run_tracked_task(draft_task(None, run_id=run.id, ticket_id=ticket_id))

    return RunTriggerResponse(run_id=run_id)


@router.get("/{ticket_id}/draft", response_model=DraftDetailResponse)
async def get_latest_draft(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(Draft)
        .where(Draft.ticket_id == ticket_id)
        .options(selectinload(Draft.citations))
        .order_by(Draft.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="No draft found for this ticket")
    return draft


@router.get("/{ticket_id}/draft/stream")
async def stream_draft(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    await get_ticket_or_404(ticket_id, db)

    draft = None
    for _ in range(DRAFT_POLL_ATTEMPTS):
        stmt = (
            select(Draft)
            .where(Draft.ticket_id == ticket_id)
            .options(selectinload(Draft.citations))
            .order_by(Draft.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()
        if draft:
            break
        await asyncio.sleep(DRAFT_POLL_INTERVAL_S)

    if not draft:
        run_id = str(uuid.uuid4())
        run = Run(
            id=run_id,
            ticket_id=ticket_id,
            run_type="draft",
            status="running",
        )
        db.add(run)
        await db.commit()

        await draft_task(None, run_id=run_id, ticket_id=ticket_id)

        stmt = (
            select(Draft)
            .where(Draft.ticket_id == ticket_id)
            .options(selectinload(Draft.citations))
            .order_by(Draft.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        draft = result.scalar_one_or_none()

    if not draft:
        raise HTTPException(status_code=500, detail="Failed to generate draft")

    async def event_generator():
        words = draft.body.split(" ") if draft.body else []
        for idx, word in enumerate(words):
            token_str = word + (" " if idx < len(words) - 1 else "")
            yield f'data: {json.dumps({"token": token_str, "done": False})}\n\n'
            await asyncio.sleep(0.02)

        cit_list = [c.doc_id for c in (draft.citations or [])]
        yield f'data: {json.dumps({"token": "", "done": True, "draft_id": draft.id, "citations": cit_list})}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{ticket_id}/actions", response_model=RunTriggerResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_action(
    ticket_id: str,
    req: ActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)
    if ticket.status in ["resolved", "closed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot propose or trigger actions on a resolved or closed ticket.",
        )

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        ticket_id=ticket_id,
        run_type="action",
        status="pending",
    )
    db.add(run)
    await db.commit()

    enqueued = False
    try:
        pool = await create_pool(WorkerSettings.redis_settings)
        await pool.enqueue_job("action_task", run_id=run.id, ticket_id=ticket_id, tool_name=req.tool_name, payload=req.payload or {})
        enqueued = True
    except Exception as exc:
        logger.warning(f"ARQ queue unavailable for action_task ({exc}), falling back to in-process task")

    if not enqueued:
        run_tracked_task(action_task(None, run_id=run.id, ticket_id=ticket_id, tool_name=req.tool_name, payload=req.payload or {}))

    return RunTriggerResponse(run_id=run_id)


@router.get("/{ticket_id}/actions", response_model=List[ActionDetailResponse])
async def list_ticket_actions(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    stmt = (
        select(ToolAction)
        .where(ToolAction.ticket_id == ticket_id)
        .options(selectinload(ToolAction.tool))
        .order_by(ToolAction.created_at)
    )
    result = await db.execute(stmt)
    actions = result.scalars().all()

    return [
        ActionDetailResponse(
            id=action.id,
            ticket_id=action.ticket_id,
            run_id=action.run_id,
            tool_id=action.tool_id,
            tool_name=action.tool.name if action.tool else None,
            payload=action.payload,
            risk_level=action.risk_level,
            status=action.status,
            idempotency_key=action.idempotency_key,
            created_at=action.created_at,
            executed_at=action.executed_at,
        )
        for action in actions
    ]


@router.get("/{ticket_id}/history", response_model=List[TimelineEventResponse])
async def get_ticket_history(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    ticket = await get_ticket_or_404(ticket_id, db)

    stmt = (
        select(AuditLog)
        .where(AuditLog.resource_type == "ticket", AuditLog.resource_id == ticket_id)
        .order_by(AuditLog.created_at.asc())
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()

    msg_stmt = (
        select(Message)
        .where(Message.ticket_id == ticket_id)
        .order_by(Message.created_at.asc())
    )
    msg_res = await db.execute(msg_stmt)
    messages = msg_res.scalars().all()

    events: List[TimelineEventResponse] = []

    events.append(
        TimelineEventResponse(
            id=f"intake-{ticket.id}",
            event_type="intake",
            title="Ticket Received & Intake Registered",
            actor_name="System Intake",
            actor_role="system",
            details=f"Subject: {ticket.subject} | Category: {ticket.category or 'general'}",
            created_at=ticket.created_at,
        )
    )

    action_title_map = {
        "ticket_assigned": "Ticket Claimed & Moved to Working Queue",
        "ticket_unassigned": "Ticket Released to Open Queue",
        "ticket_escalated": "Ticket Escalated to Senior Review",
        "ticket_closed": "Ticket Closed & Moved to Resolved Queue",
        "internal_note_added": "Internal Note Recorded",
        "security_gate_blocked": "Security Gate Triggered (Critical Threat)",
    }

    for log_entry in logs:
        title = action_title_map.get(log_entry.action, log_entry.action.replace("_", " ").title())
        events.append(
            TimelineEventResponse(
                id=log_entry.id,
                event_type=log_entry.action,
                title=title,
                actor_name=log_entry.actor_id or "System",
                actor_role="operator",
                details=f"Outcome: {log_entry.outcome}" + (f" | Risk: {log_entry.risk_level}" if log_entry.risk_level else ""),
                created_at=log_entry.created_at,
            )
        )

    for message in messages:
        if message.sender_type == "system":
            events.append(
                TimelineEventResponse(
                    id=message.id,
                    event_type="system_audit",
                    title="Audit Record",
                    actor_name="System",
                    actor_role="system",
                    details=message.content,
                    created_at=message.created_at or ticket.created_at,
                )
            )

    events.sort(key=lambda x: x.created_at)
    return events


@router.get("/{ticket_id}/notes", response_model=List[InternalNoteResponse])
async def get_ticket_notes(
    ticket_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    await get_ticket_or_404(ticket_id, db)

    stmt = (
        select(TicketNote)
        .options(selectinload(TicketNote.author))
        .where(TicketNote.ticket_id == ticket_id)
        .order_by(TicketNote.created_at.asc())
    )
    result = await db.execute(stmt)
    notes_objs = result.scalars().all()
    return [
        InternalNoteResponse(
            id=note.id,
            ticket_id=note.ticket_id,
            author_id=note.author_id,
            author_name=(note.author.name or note.author.username) if note.author else "Operator",
            author_role=note.author.role if note.author else "agent",
            content=note.content,
            created_at=note.created_at,
        )
        for note in notes_objs
    ]


@router.post("/{ticket_id}/notes", response_model=InternalNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket_note(
    ticket_id: str,
    req: InternalNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    await get_ticket_or_404(ticket_id, db)

    author_user = await db.get(User, current_user.id) if current_user and current_user.id else None
    safe_author_id = current_user.id if author_user else None

    new_note = TicketNote(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        author_id=safe_author_id,
        content=req.content.strip(),
    )
    db.add(new_note)

    await log_audit(
        db=db,
        actor_id=safe_author_id,
        action="internal_note_added",
        resource_type="ticket",
        resource_id=ticket_id,
        outcome="recorded",
    )

    await db.commit()
    await db.refresh(new_note)

    return InternalNoteResponse(
        id=new_note.id,
        ticket_id=ticket_id,
        author_id=current_user.id,
        author_name=current_user.name or current_user.username,
        author_role=current_user.role,
        content=new_note.content,
        created_at=new_note.created_at,
    )


@router.post("/{ticket_id}/refund", response_model=RefundResponse, status_code=status.HTTP_200_OK)
async def issue_refund_for_ticket(
    ticket_id: str,
    req: RefundRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["agent", "senior_agent", "admin"])),
):
    from app.services.refund_service import issue_refund_coupon

    result, is_replay = await issue_refund_coupon(
        ticket_id=ticket_id,
        amount=req.amount,
        db=db,
        idempotency_key=idempotency_key,
        actor_id=current_user.id if current_user else None,
        reason=req.reason,
    )
    if is_replay:
        response.headers["Idempotent-Replay"] = "true"
    await db.commit()
    return RefundResponse(**result)

