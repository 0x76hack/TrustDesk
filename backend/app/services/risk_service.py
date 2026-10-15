import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.ticket import Ticket
from app.models.customer import Customer
from app.models.order import Order


class RiskResult(BaseModel):
    risk_level: str
    score: int
    factors: List[Dict[str, Any]] = Field(default_factory=list)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


def score_ticket_risk(
    ticket: Ticket,
    triage_result: Any,
    retrieval_result: List[Dict[str, Any]],
    guardrail_result: Optional[Dict[str, Any]] = None,
    customer: Optional[Customer] = None,
    order: Optional[Order] = None,
    messages: Optional[List[Any]] = None,
) -> RiskResult:
    score = 0
    factors = []

    if guardrail_result and not guardrail_result.get("is_safe", True):
        return RiskResult(
            risk_level="critical",
            score=100,
            factors=[
                {
                    "name": "guardrail_block",
                    "value": guardrail_result.get("threat_type", "unsafe"),
                    "weight": 100,
                    "contribution": 100,
                }
            ],
        )

    cat = getattr(triage_result, "category", None) or (triage_result.get("category", "general") if isinstance(triage_result, dict) else "general")

    if messages is not None:
        msgs = messages
    else:
        msgs = getattr(ticket, "__dict__", {}).get("messages") or []

    msgs_text = " ".join([getattr(m, "content", "") or "" for m in msgs])
    subj = getattr(ticket, "subject", "") or ""
    full_text = f"{subj} {msgs_text}".lower()

    quality_triggers = [
        "spoil", "rancid", "sour", "curdle", "rotten", "inedible", "smell", "bad quality",
        "damage", "spill", "leak", "melt", "crush", "burst", "torn", "defect",
        "missing", "omitted", "wrong item", "refund", "compensation", "allergy", "poison"
    ]
    has_quality_trigger = False
    for qt in quality_triggers:
        if " " in qt:
            if qt in full_text:
                has_quality_trigger = True
                break
        elif re.search(rf"\b{re.escape(qt)}s?\b", full_text):
            has_quality_trigger = True
            break

    delivery_status_keywords = [
        "where", "track", "tracking", "status", "delay", "delayed", "late",
        "rider", "driver", "location", "stationary", "traffic", "rain",
        "monsoon", "transit", "eta", "delivery update", "delivery time"
    ]
    is_delivery_status = (cat == "shipping") or any(k in full_text for k in delivery_status_keywords)

    faq_keywords = [
        "membership", "pro tier", "pro", "perk", "benefit", "coupon", "stack", "hours",
        "timings", "cancellation", "policy", "faq", "how does"
    ]
    is_faq = (cat == "general") and any(k in full_text for k in faq_keywords)

    if (is_delivery_status or is_faq) and not has_quality_trigger:
        score = 10
        factor_name = "delivery_status_inquiry" if is_delivery_status else "faq_inquiry"
        factors.append({
            "name": factor_name,
            "value": "low_risk_auto_resolvable",
            "weight": 10,
            "contribution": 10,
        })
        return RiskResult(
            risk_level="low",
            score=score,
            factors=factors,
        )

    if cat == "account_security":
        val = 40
        score += val
        factors.append({"name": "ticket_category", "value": cat, "weight": 40, "contribution": val})
    elif cat == "refund":
        val = 35
        score += val
        factors.append({"name": "ticket_category", "value": cat, "weight": 35, "contribution": val})
    elif cat in ["warranty", "billing"]:
        val = 30
        score += val
        factors.append({"name": "ticket_category", "value": cat, "weight": 30, "contribution": val})

    if has_quality_trigger:
        if not any(f["name"] == "food_quality_defect" for f in factors):
            factors.append({"name": "food_quality_defect", "value": "defective_or_spoiled", "weight": 35, "contribution": 35})
        if score < 35:
            score = 35

    try:
        order_total = float(getattr(order, "total", 0.0)) if order else 0.0
    except (TypeError, ValueError):
        order_total = 0.0
    curr = getattr(order, "currency", "INR")
    currency_symbol = "₹" if str(curr) == "INR" else "$"
    if cat in ["account_security", "refund", "billing"]:
        if order_total > 500:
            val = 35
            score += val
            factors.append({"name": "monetary_exposure", "value": f"{currency_symbol}{order_total:.2f}", "weight": 35, "contribution": val})
        elif order_total > 150:
            val = 20
            score += val
            factors.append({"name": "monetary_exposure", "value": f"{currency_symbol}{order_total:.2f}", "weight": 20, "contribution": val})
    else:
        if order_total > 5000:
            val = 35
            score += val
            factors.append({"name": "monetary_exposure", "value": f"{currency_symbol}{order_total:.2f}", "weight": 35, "contribution": val})
        elif order_total > 2000:
            val = 20
            score += val
            factors.append({"name": "monetary_exposure", "value": f"{currency_symbol}{order_total:.2f}", "weight": 20, "contribution": val})

    if not retrieval_result or len(retrieval_result) == 0:
        val = 20
        score += val
        factors.append({"name": "evidence_sufficiency", "value": "zero_evidence", "weight": 20, "contribution": val})

    try:
        confidence = float(getattr(triage_result, "confidence", None) or (triage_result.get("confidence", 1.0) if isinstance(triage_result, dict) else 1.0))
    except (TypeError, ValueError):
        confidence = 1.0
    if confidence < 0.6:
        val = 15
        score += val
        factors.append({"name": "triage_confidence", "value": f"{confidence:.2f}", "weight": 15, "contribution": val})

    c_created = getattr(customer, "__dict__", {}).get("created_at") or getattr(customer, "created_at", None)
    t_created = getattr(ticket, "__dict__", {}).get("created_at") or getattr(ticket, "created_at", None)
    if c_created and t_created:
        try:
            age_days = (t_created - c_created).days
            if age_days < 1:
                val = 10
                score += val
                factors.append({"name": "account_age", "value": f"{age_days} days (new)", "weight": 10, "contribution": val})
        except Exception:
            pass

    if score < 30:
        level = "low"
    elif score < 50:
        level = "medium"
    elif score < 80:
        level = "high"
    else:
        level = "critical"

    return RiskResult(
        risk_level=level,
        score=min(score, 100),
        factors=factors,
    )
