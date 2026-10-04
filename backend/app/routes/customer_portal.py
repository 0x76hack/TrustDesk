import re
import uuid
import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.customer import Customer
from app.models.order import Order, OrderItem
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.audit_log import AuditLog
from app.models.run import Run
from app.services.audit_service import log_audit
from app.services.guardrail_service import fence_input
from app.schemas.customer import (
    CustomerLoginRequest,
    CustomerLoginResponse,
    CustomerResponse,
    CustomerTicketCreate,
)
from app.schemas.ticket import TicketResponse, TicketDetailResponse
from app.schemas.order import OrderResponse
from app.services.auth_service import (
    verify_password,
    create_customer_token,
    get_customer_by_email,
)
from app.dependencies import get_current_customer
from app.services import guardrail_service, coupon_service
from app.workers.settings import WorkerSettings
from app.workers.tasks import triage_task
from arq import create_pool

router = APIRouter()

XSS_PATTERNS = [
    r"<\s*script[^>]*>",
    r"javascript\s*:",
    r"onerror\s*=",
    r"onload\s*=",
    r"onclick\s*=",
    r"onmouseover\s*=",
    r"onfocus\s*=",
    r"<\s*img[^>]+src=[^>]+>",
    r"<\s*iframe[^>]*>",
    r"<\s*svg[^>]*>",
    r"<\s*object[^>]*>",
    r"<\s*embed[^>]*>",
    r"alert\s*\(",
    r"prompt\s*\(",
    r"confirm\s*\(",
    r"document\.(cookie|location|domain)",
    r"window\.(localStorage|sessionStorage|location)",
    r"<\s*scr<\s*script\s*>",
]

SQLI_PATTERNS = [
    r"(\b(union|select|insert|update|delete|drop|alter|truncate|create|declare|exec|execute)\b.*\b(from|into|table|database|schema|users)\b)",
    r"(\bor\b|\band\b)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+",
    r"(\bor\b|\band\b)\s+['\"][a-zA-Z0-9]+['\"]\s*=\s*['\"][a-zA-Z0-9]+",
    r";\s*drop\s+table",
    r";\s*truncate\s+table",
    r"waitfor\s+delay\s+'",
    r"sleep\s*\(\s*\d+\s*\)",
    r"benchmark\s*\(\s*\d+",
    r"--\s*$",
    r"/\*.*?\*/",
    r"'\s*or\s+'1'='1",
    r"'\s*or\s+1=1",
    r"'\s*union\s+select",
]

PATH_TRAVERSAL_PATTERNS = [
    r"(\.\./|\.\.\\|\.\.%2f|\.\.%5c){2,}",
    r"(\.\./|\.\.\\)",
    r"(/|\\)(etc/passwd|etc/shadow|boot\.ini|windows/system32|proc/self|cmd\.exe)",
]

CMD_INJECTION_PATTERNS = [
    r"(\||;|&|`|\$\()\s*(cat|whoami|id|uname|nc|netcat|curl|wget|powershell|cmd|rm|sh|bash)\b",
    r"\$\{IFS\}",
    r"\$\(printf",
]

SSRF_PATTERNS = [
    r"\b(http|https)://(127\.0\.0\.1|localhost|0\.0\.0\.0|169\.254\.\d+\.\d+|\[::1\]|2130706433|0x7f[0-9a-fA-F.]+|metadata\.google\.internal)",
    r"\b(gopher|file|ftp|dict|ldap)://",
]

NULL_BYTE_PATTERN = r"\x00|%00"


def _recursive_unquote(s: str, max_depth: int = 3) -> str:
    curr = s
    for _ in range(max_depth):
        decoded = urllib.parse.unquote(curr)
        if decoded == curr:
            break
        curr = decoded
    return curr


def validate_web_security_probe(text: str) -> Optional[str]:
    if not text:
        return None

    unquoted = _recursive_unquote(text)
    variants = [text, unquoted, text.lower(), unquoted.lower()]

    for v in variants:
        if re.search(NULL_BYTE_PATTERN, v):
            return "Null Byte Injection Probe"
        for p in XSS_PATTERNS:
            if re.search(p, v, re.IGNORECASE):
                return "Cross-Site Scripting (XSS) Injection"
        for p in SQLI_PATTERNS:
            if re.search(p, v, re.IGNORECASE):
                return "SQL Injection (SQLi) Probing"
        for p in PATH_TRAVERSAL_PATTERNS:
            if re.search(p, v, re.IGNORECASE):
                return "Directory / Path Traversal Probe"
        for p in CMD_INJECTION_PATTERNS:
            if re.search(p, v, re.IGNORECASE):
                return "Command Execution Injection"
        for p in SSRF_PATTERNS:
            if re.search(p, v, re.IGNORECASE):
                return "Server-Side Request Forgery (SSRF) Probe"
    return None


@router.post("/auth/login", response_model=CustomerLoginResponse)
async def customer_login(
    req: CustomerLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    probe = validate_web_security_probe(req.email) or validate_web_security_probe(req.password)
    if probe:
        audit = AuditLog(
            id=str(uuid.uuid4()),
            actor_id="anonymous",
            action="auth_exploit_probe_blocked",
            resource_type="customer_auth",
            resource_id=req.email[:50] if req.email else "unknown",
            outcome="rejected_at_gateway",
            risk_level="high",
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request: The submitted request could not be processed due to invalid or malformed parameters.",
        )

    customer = await get_customer_by_email(req.email.strip().lower(), db)
    if not customer or not verify_password(req.password, customer.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not customer.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer account is inactive or suspended.",
        )

    token = create_customer_token(customer)
    return CustomerLoginResponse(
        access_token=token,
        token_type="bearer",
        customer=CustomerResponse.model_validate(customer),
    )


@router.get("/auth/me", response_model=CustomerResponse)
async def customer_me(
    current_customer: Customer = Depends(get_current_customer),
):
    return CustomerResponse.model_validate(current_customer)


@router.get("/orders", response_model=List[OrderResponse])
async def customer_orders(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.customer_id == current_customer.id)
        .order_by(Order.placed_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def customer_create_ticket(
    req: CustomerTicketCreate,
    sync_process: bool = Query(False, description="Whether to execute triage synchronously before returning"),
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    for field_name, value in [("order_id", req.order_id), ("subject", req.subject), ("message", req.message)]:
        threat = validate_web_security_probe(value)
        if threat:
            ticket_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            attack_ticket = Ticket(
                id=ticket_id,
                customer_id=current_customer.id,
                order_id=req.order_id if not validate_web_security_probe(req.order_id) else None,
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

            cust_msg = Message(
                id=str(uuid.uuid4()),
                ticket_id=ticket_id,
                sender_type="customer",
                content=req.message,
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
                actor_id=current_customer.id,
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

    order_stmt = select(Order).where(Order.id == req.order_id)
    order_res = await db.execute(order_stmt)
    order = order_res.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested order not found. Please verify your order reference.",
        )

    if order.customer_id != current_customer.id:
        audit = AuditLog(
            id=str(uuid.uuid4()),
            actor_id=current_customer.id,
            action="idor_order_tamper_attempt",
            resource_type="order",
            resource_id=req.order_id,
            outcome="forbidden",
            risk_level="high",
        )
        db.add(audit)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: The requested resource is not accessible.",
        )

    combined_content = f"{req.subject}\n\n{req.message}"
    fence_res = guardrail_service.fence_input(combined_content)

    ticket_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if not fence_res.get("is_safe", True):
        ticket = Ticket(
            id=ticket_id,
            customer_id=current_customer.id,
            order_id=req.order_id,
            subject=req.subject,
            category="account_security",
            priority="urgent",
            status="escalated",
            escalation_flag=True,
            risk_level="critical",
            assigned_to=None,
            created_at=now,
            updated_at=now,
        )
        db.add(ticket)

        cust_msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            sender_type="customer",
            content=req.message,
        )
        db.add(cust_msg)

        sys_msg = Message(
            id=str(uuid.uuid4()),
            ticket_id=ticket_id,
            sender_type="system",
            content=f"SECURITY ALERT: Input fence triggered. Threat detected: {fence_res.get('threat_type')}. Adversarial payload isolated. Ticket automatically escalated with Critical Risk for Senior human security review.",
        )
        db.add(sys_msg)

        await log_audit(
            db=db,
            actor_id=current_customer.id,
            action="adversarial_prompt_injection_isolated",
            resource_type="ticket",
            resource_id=ticket_id,
            outcome="escalated_to_senior",
            risk_level="critical",
            guardrail_result=fence_res,
        )

        await db.commit()
        await db.refresh(ticket)
        return ticket

    ticket = Ticket(
        id=ticket_id,
        customer_id=current_customer.id,
        order_id=req.order_id,
        subject=req.subject,
        category=req.category or "general",
        priority="medium",
        status="open",
        escalation_flag=False,
        risk_level="low",
        assigned_to=None,
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)

    cust_msg = Message(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender_type="customer",
        content=req.message,
    )
    db.add(cust_msg)

    if req.coupon_code:
        await coupon_service.process_ticket_coupon_intake(
            ticket=ticket,
            coupon_code=req.coupon_code,
            customer_id=current_customer.id,
            order_id=req.order_id,
            db=db,
        )
    elif req.order_id and order and order.coupon_code:
        ticket.coupon_code = order.coupon_code
        ticket.coupon_discount = order.discount_amount
        ticket.coupon_status = "verified"

    run_id = str(uuid.uuid4())
    run = Run(
        id=run_id,
        ticket_id=ticket_id,
        run_type="triage",
        status="pending",
    )
    db.add(run)

    await db.commit()
    await db.refresh(ticket)

    if sync_process:
        await triage_task(None, run_id=run_id, ticket_id=ticket_id)
        await db.refresh(ticket)
        if ticket.assigned_to:
            assignee_stmt = select(Ticket).options(selectinload(Ticket.assignee)).where(Ticket.id == ticket_id)
            refreshed_res = await db.execute(assignee_stmt)
            ticket = refreshed_res.scalar_one()
            ticket.assignee_name = ticket.computed_assignee_name
    else:
        enqueued = False
        try:
            pool = await create_pool(WorkerSettings.redis_settings)
            await pool.enqueue_job("triage_task", run_id=run_id, ticket_id=ticket_id)
            enqueued = True
        except Exception as exc:
            logger.warning(f"ARQ queue unavailable for triage_task ({exc}), falling back to in-process task")

        if not enqueued:
            asyncio.create_task(triage_task(None, run_id=run_id, ticket_id=ticket_id))

    return ticket


@router.get("/tickets", response_model=List[TicketResponse])
async def customer_list_tickets(
    current_customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.assignee))
        .where(Ticket.customer_id == current_customer.id)
        .order_by(Ticket.created_at.desc())
    )
    result = await db.execute(stmt)
    tickets = result.scalars().all()
    for ticket in tickets:
        ticket.assignee_name = ticket.computed_assignee_name
    return tickets
