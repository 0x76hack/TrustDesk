import re
import json
import uuid
from typing import Dict, Any, List, AsyncGenerator, Optional, Tuple, Set
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.ai.provider_adapter import ProviderAdapter
from app.ai.model_router import ModelRouter
from app.services.guardrail_service import validate_output, scrub_pii
from app.models.draft import Draft, Citation
from app.models.kb import KBDocument
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.order import Order


class DraftResult(BaseModel):
    draft_id: Optional[str] = None
    body: str
    citations: List[str] = Field(default_factory=list)
    status: str
    model_used: Optional[str] = None
    token_usage: Optional[Dict[str, Any]] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


def build_draft_prompts(
    ticket: Ticket,
    customer: Optional[Customer],
    order: Optional[Order],
    retrieval_results: List[Dict[str, Any]],
    customer_message: Optional[str] = None,
) -> Tuple[str, str]:
    sys_prompt = (
        "You are TrustDesk's AI Customer Operations Specialist for food delivery customer care.\n"
        "Your mission is to provide complete, thorough, helpful, empathetic, and comprehensive responses to customer inquiries.\n\n"
        "CORE QUALITY GUIDELINES:\n"
        "1. COMPLETE, SELF-CONTAINED ANSWERS: You must fully answer the customer's question directly. Provide all relevant facts, explanations, status details, and next steps in the body of your message. NEVER give half-baked, terse, or evasive responses. NEVER tell the customer to 'go read' a policy or merely cite a document without explaining the full answer.\n"
        "2. CONCRETE ORDER CONTEXT: Always reference the specific order details when available — such as the restaurant name, ordered food items, delivery partner name, live status, and addresses. Make the customer feel personally attended to.\n"
        "3. GROUNDING WITH CITATIONS: Ground your factual statements using the provided Knowledge Base passages. Place the citation tag [DOC doc_id] next to the specific claims or at the end of the explanation, but the explanation itself must be comprehensive and crystal clear.\n"
        "4. DELIVERY DELAYS & STATUS: Explain clearly what the courier is doing, reason for any delay (weather/traffic/prep), estimated arrival time, and assure them that their food is stored in insulated bags to arrive fresh and hot.\n"
        "5. MEMBERSHIP & BENEFITS: Explain all membership perks in detail (e.g. Pro Tier unlimited free delivery on orders above ₹149, stacking with coupons, no surge pricing), explaining exactly how to apply codes at checkout.\n"
        "6. TONE: Warm, professional, reassuring, and attentive (top-tier executive customer care standard).\n"
        "7. TEMPORAL WINDOWS: When evaluating policy eligibility windows (returns, replacements), evaluate elapsed time between Order Delivered At and Ticket Created At."
    )

    doc_text = ""
    for r in retrieval_results:
        doc_text += f"\n[DOC {r['doc_id']}]\n{r['content']}\n"

    cust_name = getattr(customer, "name", "Customer") if customer else "Customer"
    order_id = getattr(order, "id", "None") if order else "None"
    order_status = getattr(order, "status", "N/A") if order else "N/A"
    order_restaurant = getattr(order, "restaurant", "Partner Restaurant") if order else "Partner Restaurant"
    order_placed_val = getattr(order, "placed_at", None) if order else None
    order_placed = order_placed_val.isoformat() if order_placed_val else "N/A"
    order_delivered_val = getattr(order, "delivered_at", None) if order else None
    order_delivered = order_delivered_val.isoformat() if order_delivered_val else "N/A"
    ticket_created_val = getattr(ticket, "created_at", None) if ticket else None
    ticket_created = ticket_created_val.isoformat() if ticket_created_val else "N/A"
    live_status_msg = getattr(order, "live_status_message", "") if order else ""
    delay_reason = getattr(order, "delay_reason", "") if order else ""
    delivery_partner = getattr(order, "delivery_partner_name", "Assigned Delivery Partner") if order else "Assigned Delivery Partner"
    delivery_addr = (getattr(order, "delivery_address", "") or getattr(customer, "address", "")) if (order or customer) else ""

    items_list = []
    if order:
        order_dict = getattr(order, "__dict__", {})
        raw_items = order_dict.get("items")
        if raw_items:
            items_list = [f"{getattr(itm, 'quantity', 1)}x {getattr(itm, 'item_name', 'item')}" for itm in raw_items]
    items_summary = ", ".join(items_list) if items_list else "your ordered meal"

    inquiry_text = customer_message or getattr(ticket, "subject", "") or ""

    user_prompt = (
        f"Customer Name: {cust_name}\n"
        f"Order ID: {order_id}\n"
        f"Restaurant: {order_restaurant}\n"
        f"Order Status: {order_status}\n"
        f"Ordered Items: {items_summary}\n"
        f"Delivery Address: {delivery_addr}\n"
        f"Delivery Partner: {delivery_partner}\n"
        f"Order Placed At: {order_placed}\n"
        f"Order Delivered At: {order_delivered}\n"
        f"Ticket Created At: {ticket_created}\n"
        f"Live Status Update: {live_status_msg}\n"
        f"Delay Reason: {delay_reason}\n"
        f"Customer Inquiry: \"{inquiry_text}\"\n"
        f"Ticket Subject: {getattr(ticket, 'subject', '') or ''}\n\n"
        f"Relevant Knowledge Base Policies:\n{doc_text}\n\n"
        f"Draft a context-aware, empathetic, and comprehensive response that directly and completely answers the customer's query:"
    )
    return sys_prompt, user_prompt


async def extract_and_verify_citations(
    content: str,
    retrieval_results: List[Dict[str, Any]],
    db: AsyncSession,
) -> Set[str]:
    raw_doc_ids = set(re.findall(r"\[DOC ([a-zA-Z0-9_-]+)\]", content))
    if not raw_doc_ids or not retrieval_results:
        return set()

    allowed_doc_ids = {r["doc_id"] for r in retrieval_results if "doc_id" in r}
    verified_candidate_ids = raw_doc_ids.intersection(allowed_doc_ids)
    if not verified_candidate_ids:
        return set()

    docs_check = await db.execute(
        select(KBDocument.doc_id).where(
            KBDocument.doc_id.in_(verified_candidate_ids),
            KBDocument.is_adversarial.is_(False),
        )
    )
    return set(docs_check.scalars().all())


async def generate_draft(
    ticket: Ticket,
    customer: Optional[Customer],
    order: Optional[Order],
    retrieval_results: List[Dict[str, Any]],
    triage_result: Any,
    risk_result: Any,
    provider: ProviderAdapter,
    model_router: ModelRouter,
    db: AsyncSession,
    run_id: Optional[str] = None,
    customer_message: Optional[str] = None,
) -> DraftResult:

    if not retrieval_results:
        refusal_content = (
            "Thank you for contacting customer support. We are unable to synthesize an automated policy-verified "
            "response as there are no authoritative knowledge base documents matching your inquiry. Your ticket "
            "has been routed to our senior operations team for review."
        )
        draft_id = str(uuid.uuid4())
        draft = Draft(
            id=draft_id,
            ticket_id=ticket.id,
            run_id=run_id,
            body=refusal_content,
            status="insufficient_evidence",
        )
        db.add(draft)
        await db.flush()
        return DraftResult(
            draft_id=draft_id,
            body=refusal_content,
            citations=[],
            status="insufficient_evidence",
            model_used="deterministic-grounding-gate",
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    sys_prompt, user_prompt = build_draft_prompts(
        ticket=ticket,
        customer=customer,
        order=order,
        retrieval_results=retrieval_results,
        customer_message=customer_message,
    )

    model = model_router.route("draft")
    model_used = model
    token_usage = {"prompt_tokens": 120, "completion_tokens": 80, "total_tokens": 200}
    try:
        response = await provider.complete(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
        )
        content = response.content
        model_used = response.model_used
        token_usage = response.token_usage
        if len(content.strip().split()) < 15:
            raise ValueError("Response too brief")
    except Exception:
        # Never replace a failed model call with an invented policy answer.
        # Keep the ticket in a human-reviewable state instead.
        failure_content = (
            "We could not generate a grounded response right now. No policy claims "
            "or citations were generated. Please route this ticket to a human agent "
            "for review."
        )
        draft_id = str(uuid.uuid4())
        db.add(Draft(
            id=draft_id,
            ticket_id=ticket.id,
            run_id=run_id,
            body=failure_content,
            status="generation_failed",
        ))
        await db.flush()
        return DraftResult(
            draft_id=draft_id,
            body=failure_content,
            citations=[],
            status="generation_failed",
            model_used=model_used,
            token_usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )

    val_res = validate_output(content)
    if not val_res["is_safe"]:
        return DraftResult(
            draft_id=None,
            body="Draft generation blocked due to safety policy violation.",
            citations=[],
            status="blocked",
        )

    content = scrub_pii(content)
    valid_doc_ids = await extract_and_verify_citations(content, retrieval_results, db)

    draft_id = str(uuid.uuid4())
    draft = Draft(
        id=draft_id,
        ticket_id=ticket.id,
        run_id=run_id,
        body=content,
        status="ready",
    )
    db.add(draft)

    for d_id in valid_doc_ids:
        cit = Citation(
            id=str(uuid.uuid4()),
            draft_id=draft_id,
            doc_id=d_id,
            relevance_score=1.0,
        )
        db.add(cit)

    await db.flush()

    return DraftResult(
        draft_id=draft_id,
        body=content,
        citations=list(valid_doc_ids),
        status="ready",
        model_used=model_used,
        token_usage=token_usage,
    )


async def stream_draft(
    ticket: Ticket,
    customer: Optional[Customer],
    order: Optional[Order],
    retrieval_results: List[Dict[str, Any]],
    triage_result: Any,
    risk_result: Any,
    provider: ProviderAdapter,
    model_router: ModelRouter,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    sys_prompt, user_prompt = build_draft_prompts(
        ticket=ticket,
        customer=customer,
        order=order,
        retrieval_results=retrieval_results,
    )

    model = model_router.route("draft")
    full_content = ""
    async for token in provider.complete_stream(
        [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
    ):
        full_content += token
        yield f'data: {json.dumps({"token": token})}\n\n'

    draft_id = str(uuid.uuid4())
    raw_ids = set(re.findall(r"\[DOC ([a-zA-Z0-9_-]+)\]", full_content))
    allowed_ids = {r["doc_id"] for r in retrieval_results if "doc_id" in r}
    doc_ids = list(raw_ids.intersection(allowed_ids))

    yield f'data: {json.dumps({"done": True, "draft_id": draft_id, "citations": doc_ids})}\n\n'
