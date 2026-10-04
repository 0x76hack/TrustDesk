from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RunResponse(BaseModel):
    id: str
    ticket_id: Optional[str] = None
    run_type: str
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"from_attributes": True}
