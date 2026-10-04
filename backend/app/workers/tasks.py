import time
import uuid
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import AsyncSessionLocal
from app.models.ticket import Ticket
from app.models.message import Message
from app.models.customer import Customer
from app.models.order import Order
from app.models.run import Run
from app.models.user import User
from app.ai.openrouter import OpenRouterProvider
from app.ai.model_router import ModelRouter
from app.config import settings

from app.services import (
    triage_service,
    risk_service,
    retrieval_service,
    draft_service,
    action_service,
    guardrail_service,
    trace_service,
    eval_service,
)


def get_ai_provider():
    return OpenRouterProvider(api_key=settings.OPENROUTER_API_KEY or "", base_url=settings.OPENROUTER_BASE_URL)


model_router = ModelRouter()


def create_system_message(ticket_id: str, content: str) -> Message:
    return Message(
        id=str(uuid.uuid4()),
        ticket_id=ticket_id,
        sender_type="system",
        content=content,
    )


async def _execute_triage_pipeline(
    ticket: Ticket,
    messages: List[Message],
    first_msg: str,
    provider,
    db: AsyncSession,
    customer: Optional[Customer] = None,
    order: Optional[Order] = None,
) -> Tuple[Dict[str, Any], Any, List[Dict[str, Any]], Any]:
    full_text = f"{ticket.subject}\n{first_msg}".strip()
    guard_res = guardrail_service.fence_input(full_text)
    triage_res = await triage_service.triage_ticket(ticket, messages, provider, model_router)
    retrieval_res = await retrieval_service.retrieve_context(
        query=first_msg or ticket.subject,
        category=triage_res.get("category", "general"),
        db=db,
        provider=provider,
    )
    cust = customer if customer is not None else getattr(ticket, "__dict__", {}).get("customer")
    ord_obj = order if order is not None else getattr(ticket, "__dict__", {}).get("order")

    risk_res = risk_service.score_ticket_risk(
        ticket=ticket,
        triage_result=triage_res,
        retrieval_result=retrieval_res,
        guardrail_result=guard_res,
        customer=cust,
        order=ord_obj,
        messages=messages,
    )
    return guard_res, triage_res, retrieval_res, risk_res


async def _apply_triage_decisions(
    ticket: Ticket,
    ticket_id: str,
    messages: List[Message],
    first_msg: str,
    guard_res: Dict[str, Any],
    triage_res: Any,
    retrieval_res: List[Dict[str, Any]],
    risk_res: Any,
    provider,
    db: AsyncSession,
    run_id: str,
    customer: Optional[Customer] = None,
    order: Optional[Order] = None,
) -> None:
    if not guard_res.get("is_safe", True):
        ticket.category = "account_security"
        ticket.priority = "urgent"
        ticket.risk_level = "critical"
        ticket.escalation_flag = True
        ticket.status = "escalated"
        ticket.assigned_to = None

        has_warn = any("SECURITY ALERT" in (m.content or "") for m in messages)
        if not has_warn:
            sys_msg = create_system_message(
                ticket_id=ticket_id,
                content=f"SECURITY ALERT: Input fence triggered. Threat detected: {guard_res.get('threat_type')}. Details: {guard_res.get('details')}. Automatically escalated with Critical Risk.",
            )
            db.add(sys_msg)
        return

    ticket.category = triage_res.get("category", "general")
    ticket.priority = triage_res.get("priority", "medium")
    ticket.risk_level = risk_res.get("risk_level", "low")
    ticket.escalation_flag = triage_res.get("escalation_needed", False) or (ticket.risk_level == "critical")

    if ticket.escalation_flag or ticket.risk_level == "critical":
        ticket.status = "escalated"
        ticket.assigned_to = None
    elif ticket.risk_level == "low" and not ticket.escalation_flag:
        text_check = f"{getattr(ticket, 'subject', '') or ''} {first_msg or ''}".lower()
        human_triggers = [
            "spoil", "rancid", "sour", "curdle", "rotten", "inedible", "smell",
            "damage", "spill", "leak", "melt", "crush", "burst", "torn",
            "defect", "broken", "missing", "omitted", "forgot", "wrong",
            "refund", "replace", "compensation", "money", "stolen", "charge",
            "allergy", "poison", "sick", "doctor", "hospital", "emergency room", "in the er",
            "emergency", "urgent", "hack", "breach", "threat"
        ]
        has_human_trigger = False
        for ht in human_triggers:
            if " " in ht:
                if ht in text_check:
                    has_human_trigger = True
                    break
            elif re.search(rf"\b{re.escape(ht)}s?\b", text_check):
                has_human_trigger = True
                break

        is_pure_faq = False
        if ticket.category == "shipping" or any(k in text_check for k in ["where", "track", "tracking", "status", "delay", "delayed", "late", "rider", "driver", "location", "transit", "rain", "monsoon", "traffic", "stationary", "eta"]):
            is_pure_faq = True
        elif ticket.category == "general" or any(k in text_check for k in ["membership", "pro tier", "pro", "perk", "benefit", "coupon", "stack", "hours", "how does", "policy", "faq"]):
            is_pure_faq = True

        is_auto_candidate = (
            not has_human_trigger
            and is_pure_faq
        )
        if is_auto_candidate:
            try:
                cust = customer if customer is not None else getattr(ticket, "__dict__", {}).get("customer")
                ord_obj = order if order is not None else getattr(ticket, "__dict__", {}).get("order")

                draft_res = await draft_service.generate_draft(
                    ticket=ticket,
                    customer=cust,
                    order=ord_obj,
                    retrieval_results=retrieval_res,
                    triage_result=triage_res,
                    risk_result=risk_res,
                    provider=provider,
                    model_router=model_router,
                    db=db,
                    run_id=run_id,
                    customer_message=first_msg,
                )
                if draft_res.get("body") and draft_res.get("status") != "blocked":
                    ai_body = draft_res["body"].strip()
                    ai_msg = Message(
                        id=str(uuid.uuid4()),
                        ticket_id=ticket_id,
                        sender_type="agent",
                        content=f"{ai_body}\n\n[Automated AI Support Resolution - Policy Verified]",
                    )
                    db.add(ai_msg)
                    ai_user_res = await db.execute(select(User).where(User.username == "ai_agent"))
                    ai_user = ai_user_res.scalars().first()
                    if not ai_user:
                        ai_user = User(
                            id=str(uuid.uuid4()),
                            username="ai_agent",
                            name="TrustDesk AI Agent",
                            email="ai.agent@trustdesk.local",
                            password_hash="ai_agent_hash",
                            role="agent",
                        )
                        db.add(ai_user)
                        await db.flush()
                    ticket.assigned_to = ai_user.id
                    ticket.assigned_at = datetime.now(timezone.utc)
                    ticket.status = "resolved"
                    ticket.resolved_at = datetime.now(timezone.utc)
                    close_audit_msg = create_system_message(
                        ticket_id=ticket_id,
                        content="Ticket automatically resolved and closed by AI Agent (Policy Verified FAQ).",
                    )
                    db.add(close_audit_msg)
            except Exception as e:
                import traceback
                print(f"[AUTO-RESOLVE ERROR] {ticket_id}: {e}\n{traceback.format_exc()}")
                ticket.status = "open"
        else:
            ticket.status = "open"
    else:
        ticket.status = "open"


async def triage_task(ctx, run_id: str, ticket_id: str):
    start_time = time.time()

    async with AsyncSessionLocal() as db:
        try:
            provider = get_ai_provider()
            run_res = await db.execute(select(Run).where(Run.id == run_id))
            run = run_res.scalar_one_or_none()
            if run:
                run.status = "running"
                await db.flush()

            ticket_res = await db.execute(
                select(Ticket)
                .where(Ticket.id == ticket_id)
                .options(
                    selectinload(Ticket.messages),
                    selectinload(Ticket.customer),
                    selectinload(Ticket.order).selectinload(Order.items),
                )
            )
            ticket = ticket_res.scalar_one_or_none()
            if not ticket:
                if run:
                    run.status = "failed"
                    run.error = f"Ticket {ticket_id} not found"
                    await db.commit()
                return

            messages = ticket.messages or []
            first_msg = messages[0].content if messages else ""

            guard_res, triage_res, retrieval_res, risk_res = await _execute_triage_pipeline(
                ticket, messages, first_msg, provider, db, customer=ticket.customer, order=ticket.order
            )

            await _apply_triage_decisions(
                ticket, ticket_id, messages, first_msg, guard_res, triage_res, retrieval_res, risk_res, provider, db, run_id, customer=ticket.customer, order=ticket.order
            )

            latency_ms = int((time.time() - start_time) * 1000)
            await trace_service.record_trace(
                run_id=run_id,
                ticket_id=ticket_id,
                run_type="triage",
                retrieved_doc_ids=[r["doc_id"] for r in retrieval_res],
                tool_actions=None,
                risk_level=ticket.risk_level,
                risk_factors=risk_res.get("factors"),
                guardrail_result=guard_res,
                final_status=ticket.status,
                model_used=model_router.route("triage"),
                token_usage={"tokens": 150},
                latency_ms=latency_ms,
                db=db,
            )

            if run:
                run.status = "completed"

            await db.commit()

        except Exception as e:
            await db.rollback()
            if run:
                run.status = "failed"
                run.error = str(e)
                await db.commit()
            raise


async def draft_task(ctx, run_id: str, ticket_id: str):
    start_time = time.time()

    async with AsyncSessionLocal() as db:
        try:
            provider = get_ai_provider()
            run_res = await db.execute(select(Run).where(Run.id == run_id))
            run = run_res.scalar_one_or_none()
            if run:
                run.status = "running"
                await db.flush()

            ticket_res = await db.execute(
                select(Ticket)
                .where(Ticket.id == ticket_id)
                .options(
                    selectinload(Ticket.messages),
                    selectinload(Ticket.customer),
                    selectinload(Ticket.order).selectinload(Order.items),
                )
            )
            ticket = ticket_res.scalar_one_or_none()
            if not ticket:
                if run:
                    run.status = "failed"
                    run.error = f"Ticket {ticket_id} not found"
                    await db.commit()
                return

            messages = ticket.messages or []
            first_msg = messages[0].content if messages else ""
            full_text = f"{ticket.subject}\n{first_msg}".strip()

            guard_res = guardrail_service.fence_input(full_text)

            retrieval_res = await retrieval_service.retrieve_context(
                query=first_msg or ticket.subject, category=ticket.category or "general", db=db, provider=provider
            )

            risk_res = risk_service.score_ticket_risk(
                ticket=ticket,
                triage_result={"category": ticket.category, "confidence": 0.9},
                retrieval_result=retrieval_res,
                guardrail_result=guard_res,
                customer=ticket.customer,
                order=ticket.order,
            )

            draft_res = await draft_service.generate_draft(
                ticket=ticket,
                customer=ticket.customer,
                order=ticket.order,
                retrieval_results=retrieval_res,
                triage_result={"category": ticket.category},
                risk_result=risk_res,
                provider=provider,
                model_router=model_router,
                db=db,
                run_id=run_id,
                customer_message=first_msg,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            await trace_service.record_trace(
                run_id=run_id,
                ticket_id=ticket_id,
                run_type="draft",
                retrieved_doc_ids=[r["doc_id"] for r in retrieval_res],
                tool_actions=None,
                risk_level=ticket.risk_level,
                risk_factors=risk_res.get("factors"),
                guardrail_result=guard_res,
                final_status=ticket.status,
                model_used=draft_res.get("model_used", model_router.route("draft")),
                token_usage=draft_res.get("token_usage"),
                latency_ms=latency_ms,
                db=db,
            )

            if run:
                run.status = "completed"

            await db.commit()

        except Exception as e:
            await db.rollback()
            if run:
                run.status = "failed"
                run.error = str(e)
                await db.commit()
            raise


async def action_task(ctx, run_id: str, ticket_id: str, tool_name: str, payload: dict):
    start_time = time.time()

    async with AsyncSessionLocal() as db:
        try:
            run_res = await db.execute(select(Run).where(Run.id == run_id))
            run = run_res.scalar_one_or_none()
            if run:
                run.status = "running"
                await db.flush()

            ticket_res = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
            ticket = ticket_res.scalar_one_or_none()
            if not ticket:
                if run:
                    run.status = "failed"
                    run.error = f"Ticket {ticket_id} not found"
                    await db.commit()
                return

            action = await action_service.recommend_action(
                ticket=ticket,
                triage_result={"category": ticket.category or "general"},
                risk_result={"risk_level": ticket.risk_level or "low"},
                db=db,
                run_id=run_id,
            )

            latency_ms = int((time.time() - start_time) * 1000)
            await trace_service.record_trace(
                run_id=run_id,
                ticket_id=ticket_id,
                run_type="action",
                retrieved_doc_ids=None,
                tool_actions=[{"id": action.id, "tool_id": action.tool_id, "status": action.status}] if action else None,
                risk_level=ticket.risk_level,
                risk_factors=None,
                guardrail_result=None,
                final_status=ticket.status,
                model_used=None,
                token_usage=None,
                latency_ms=latency_ms,
                db=db,
            )

            if run:
                run.status = "completed"

            await db.commit()

        except Exception as e:
            await db.rollback()
            if run:
                run.status = "failed"
                run.error = str(e)
                await db.commit()
            raise


async def eval_task(ctx, eval_run_id: str):
    async with AsyncSessionLocal() as db:
        try:
            provider = get_ai_provider()
            eval_cases = []
            possible_paths = [
                Path("data/eval_cases.jsonl"),
                Path(__file__).resolve().parents[3] / "data" / "eval_cases.jsonl",
                Path(__file__).resolve().parents[2] / "data" / "eval_cases.jsonl",
            ]
            for p in possible_paths:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                eval_cases.append(json.loads(line))
                    if eval_cases:
                        break

            if not eval_cases:
                eval_cases = [
                    {"id": "eval_001", "text": "Food delayed", "expected": {"category": "shipping", "priority": "low", "escalated": False, "citations": ["KB-SHIPPING-001"]}},
                    {"id": "eval_002", "text": "Food cold", "expected": {"category": "refund", "priority": "medium", "escalated": False, "citations": ["KB-REFUND-001"]}},
                ]

            await eval_service.run_evaluation(eval_cases, db, provider, eval_run_id=eval_run_id)
            await db.commit()
        except Exception as e:
            await db.rollback()
            run_res = await db.execute(select(Run).where(Run.id == eval_run_id))
            run = run_res.scalar_one_or_none()
            if run:
                run.status = "failed"
                run.error = str(e)
                await db.commit()
            raise
