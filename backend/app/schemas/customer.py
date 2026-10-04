from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CustomerCreate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    membership_tier: Optional[str] = "Standard"
    password: Optional[str] = None


class CustomerResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    membership_tier: Optional[str] = "Standard"
    total_orders: Optional[int] = 1
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CustomerLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=100)


class CustomerLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerResponse


class CustomerTicketCreate(BaseModel):
    order_id: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Za-z0-9\-_]+$")
    subject: str = Field(..., min_length=3, max_length=200)
    message: str = Field(..., min_length=5, max_length=4000)
    category: Optional[str] = "general"
    coupon_code: Optional[str] = None
