import uuid
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog


async def log_audit(
    db: AsyncSession,
    action: str,
    resource_type: str,
    actor_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    outcome: str = "success",
    risk_level: Optional[str] = None,
    guardrail_result: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    clean_actor = str(actor_id)[:100] if actor_id else None
    clean_resource = str(resource_id)[:100] if resource_id else None
    clean_outcome = str(outcome or "success")[:100]
    entry = AuditLog(
        id=str(uuid.uuid4()),
        actor_id=clean_actor,
        action=str(action)[:100],
        resource_type=str(resource_type)[:50],
        resource_id=clean_resource,
        outcome=clean_outcome,
        risk_level=risk_level,
        guardrail_result=guardrail_result,
    )
    db.add(entry)
    return entry
