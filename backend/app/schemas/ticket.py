from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from .customer import CustomerResponse
from .order import OrderResponse


class TicketCreate(BaseModel):
    customer_id: str
    order_id: Optional[str] = None
    subject: str
    message: str
    category: Optional[str] = None
    priority: Optional[str] = None
    coupon_code: Optional[str] = None



class MessageCreate(BaseModel):
    content: str
    sender_type: str = "customer"


class MessageResponse(BaseModel):
    id: str
    ticket_id: str
    sender_type: str
    content: str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TicketResponse(BaseModel):
    id: str
    customer_id: str
    order_id: Optional[str] = None
    subject: str
    category: Optional[str] = None
    priority: Optional[str] = None
    status: str
    escalation_flag: bool = False
    risk_level: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    first_response_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    notes: Optional[str] = None
    assignee_name: Optional[str] = None
    coupon_code: Optional[str] = None
    coupon_discount: Optional[float] = None
    coupon_status: Optional[str] = None
    coupon_abuse_flag: bool = False
    close_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TicketDetailResponse(TicketResponse):
    customer: Optional[CustomerResponse] = None
    order: Optional[OrderResponse] = None
    messages: List[MessageResponse] = Field(default_factory=list)


class TriageRequest(BaseModel):
    force_refresh: bool = False


class RunTriggerResponse(BaseModel):
    run_id: str


class TriageResponse(RunTriggerResponse):
    pass


class TicketAssignRequest(BaseModel):
    user_id: Optional[str] = None


class TicketUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    escalation_flag: Optional[bool] = None


class TicketEscalateRequest(BaseModel):
    reason: str
    custom_reason: Optional[str] = None
    note: Optional[str] = None


class TicketCloseRequest(BaseModel):
    notes: str = Field(..., description="Resolution notes explaining the closure")
    resolution_type: Optional[str] = Field("resolved", description="Closing outcome code")
    custom_resolution: Optional[str] = None


class InternalNoteCreate(BaseModel):
    content: str


class InternalNoteResponse(BaseModel):
    id: str
    ticket_id: str
    author_id: Optional[str] = None
    author_name: str
    author_role: str
    content: str
    created_at: datetime


class TimelineEventResponse(BaseModel):
    id: str
    event_type: str
    title: str
    actor_name: Optional[str] = None
    actor_role: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime


class RefundRequest(BaseModel):
    amount: float = Field(..., gt=0)
    reason: Optional[str] = None


class RefundResponse(BaseModel):
    coupon_code: str
    amount: float
    ticket_id: str
    order_id: Optional[str] = None
    status: str = "issued"
    message: Optional[str] = None



