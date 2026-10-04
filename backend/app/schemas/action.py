from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class ActionRequest(BaseModel):
    tool_name: str
    payload: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class ActionResponse(BaseModel):
    run_id: str


class ActionDetailResponse(BaseModel):
    id: str
    ticket_id: str
    run_id: Optional[str] = None
    tool_id: str
    tool_name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    risk_level: Optional[str] = None
    status: str
    idempotency_key: Optional[str] = None
    created_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
