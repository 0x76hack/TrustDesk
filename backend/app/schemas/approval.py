from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ApprovalRequest(BaseModel):
    decision: str
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    action_id: str
    approver_id: str
    decision: str
    reason: Optional[str] = None
    decided_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
