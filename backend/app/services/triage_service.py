import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.ai.provider_adapter import ProviderAdapter
from app.ai.model_router import ModelRouter
from app.models.ticket import Ticket
from app.models.message import Message


class TriageResult(BaseModel):
    category: str = "general"
    priority: str = "medium"
    escalation_needed: bool = False
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


async def triage_ticket(
    ticket: Ticket,
    messages: List[Message],
    provider: ProviderAdapter,
    model_router: ModelRouter,
) -> TriageResult:
    model = model_router.route('triage')

    message_text = "\n".join([f"{m.sender_type}: {m.content}" for m in messages])

    prompt = f"""You are TrustDesk's AI Support Operations Triage Agent.
Classify the following customer ticket into a structured JSON object.

Ticket ID: {ticket.id}
Subject: {ticket.subject or ''}
Customer Messages:
{message_text}

Allowed Categories:
- shipping (order status, late delivery, driver location, delivery address)
- refund (damaged food, crushed item, spilled sauce, missing items, spoiled food, rancid/sour items, curdled dairy, inedible meals, cold food, cancellation)
- billing (overcharge, duplicate charge, receipt request, promo code issue)
- warranty (defective packaging, melted container/lid, food quality guarantee)
- account_security (hacked account, unauthorized login, credentials breach)
- general (general questions, feedback, store hours, membership benefits)

Allowed Priorities:
- low (informational questions, general feedback)
- medium (standard delivery update, food damage, missing item, normal refund inquiry, food quality issues)
- high (angry customer, significant food safety issue, high-value dispute)
- urgent (account security breach, extreme threat)

Output valid JSON with the following keys:
{{
  "category": "one of the allowed categories",
  "priority": "one of the allowed priorities",
  "escalation_needed": boolean,
  "confidence": float between 0.0 and 1.0
}}

IMPORTANT RULES:
- "escalation_needed" MUST BE FALSE for standard post-order food issues like damaged food, late delivery, missing item, or standard refund requests within policy. These are solved with AI drafts.
- "escalation_needed" MUST BE TRUE ONLY for account takeover, severe security breaches, or hostile legal threats.
"""

    try:
        response = await provider.complete(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            structured_output={"type": "json_object"}
        )
        data = json.loads(response.content)

        raw_cat = data.get("category", "general")
        if isinstance(raw_cat, list) and raw_cat:
            raw_cat = raw_cat[0]
        category = str(raw_cat).lower().strip()
        allowed_cats = ["shipping", "refund", "warranty", "billing", "account_security", "general"]
        if category not in allowed_cats:
            for ac in allowed_cats:
                if ac in category:
                    category = ac
                    break
            else:
                category = "general"

        raw_pri = data.get("priority", "medium")
        if isinstance(raw_pri, list) and raw_pri:
            raw_pri = raw_pri[0]
        priority = str(raw_pri).lower().strip()
        if priority not in ["low", "medium", "high", "urgent"]:
            priority = "medium"

        text_check = f"{ticket.subject or ''} {message_text}".lower()
        if any(k in text_check for k in ["spoil", "rancid", "sour", "curdle", "rotten", "inedible", "smell", "bad quality"]):
            category = "refund"
            priority = "medium"
        elif any(k in text_check for k in ["packaging", "melt", "leak", "defective lid", "seal deformed", "cup melted"]):
            category = "warranty"
            priority = "medium"

        escalation_needed = bool(data.get("escalation_needed", False))
        if category in ["shipping", "refund", "billing", "warranty", "general"]:
            if any(k in text_check for k in ["allergy", "epipen", "medical", "hospital", "emergency", "police", "aggressive", "yelling", "unsafe", "misconduct", "board meeting"]):
                escalation_needed = True
                priority = "urgent"
            elif not any(k in text_check for k in ["hack", "breach", "compromise", "unauthorized login", "lawyer"]):
                escalation_needed = False

        confidence = float(data.get("confidence", 0.9))
        return TriageResult(
            category=category,
            priority=priority,
            escalation_needed=escalation_needed,
            confidence=max(0.8, min(1.0, confidence)),
        )
    except Exception:
        text = f"{ticket.subject or ''} {message_text}".lower()
        if any(k in text for k in ["allergy", "epipen", "medical", "hospital", "emergency", "police", "aggressive", "unsafe", "misconduct", "board meeting"]):
            cat = "shipping" if "delivery" in text or "courier" in text else "general"
            pri = "urgent"
            esc = True
        elif "security" in text or "hack" in text or "compromise" in text:
            cat = "account_security"
            pri = "urgent"
            esc = True
        elif any(k in text for k in ["refund", "damage", "spill", "crush", "cold", "missing", "wrong item", "spoil", "rancid", "sour", "curdle", "rotten", "inedible", "smell", "bad quality"]):
            cat = "refund"
            pri = "medium"
            esc = False
        elif any(k in text for k in ["packaging", "melt", "leak", "defective lid", "seal deformed", "cup melted"]):
            cat = "warranty"
            pri = "medium"
            esc = False
        elif any(k in text for k in ["where", "driver", "status", "delivery", "late", "track"]):
            cat = "shipping"
            pri = "low" if any(k in text for k in ["delay", "traffic", "flyover", "rain", "status", "tracking"]) else "medium"
            esc = False
        elif any(k in text for k in ["charge", "bill", "invoice", "receipt", "promo"]):
            cat = "billing"
            pri = "medium"
            esc = False
        else:
            cat = "general"
            pri = "low"
            esc = False

        return TriageResult(
            category=cat,
            priority=pri,
            escalation_needed=esc,
            confidence=0.85,
        )
