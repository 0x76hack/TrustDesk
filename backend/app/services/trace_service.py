import uuid
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.trace import Trace


async def record_trace(
    run_id: str,
    ticket_id: Optional[str],
    run_type: str,
    retrieved_doc_ids: Optional[List[str]],
    tool_actions: Optional[List[Dict[str, Any]]],
    risk_level: Optional[str],
    risk_factors: Optional[List[Dict[str, Any]]],
    guardrail_result: Optional[Dict[str, Any]],
    final_status: str,
    model_used: Optional[str],
    token_usage: Optional[Dict[str, Any]],
    latency_ms: Optional[int],
    db: AsyncSession,
) -> Trace:
    trace = Trace(
        id=str(uuid.uuid4()),
        run_id=run_id,
        ticket_id=ticket_id,
        run_type=run_type,
        retrieved_doc_ids={"doc_ids": retrieved_doc_ids} if retrieved_doc_ids else None,
        tool_actions_json={"actions": tool_actions} if tool_actions else None,
        risk_level=risk_level,
        risk_factors={"factors": risk_factors} if risk_factors else None,
        guardrail_result=guardrail_result,
        final_status=final_status,
        model_used=model_used,
        token_usage=token_usage,
        latency_ms=latency_ms,
    )
    db.add(trace)
    await db.flush()
    return trace
