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
    entry = AuditLog(
        id=str(uuid.uuid4()),
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        risk_level=risk_level,
        guardrail_result=guardrail_result,
    )
    db.add(entry)
    return entry
