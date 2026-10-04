from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CouponCreate(BaseModel):
    customer_id: str
    amount: float = Field(gt=0)
    original_order_id: Optional[str] = None
    ticket_id: Optional[str] = None
    currency: str = "INR"


class CouponRedeemRequest(BaseModel):
    coupon_code: str
    order_id: str
    idempotency_key: Optional[str] = None


class CouponResponse(BaseModel):
    id: str
    code: str
    customer_id: str
    original_order_id: Optional[str] = None
    ticket_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    redeemed_order_id: Optional[str] = None
    redeemed_at: Optional[datetime] = None
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponRedeemResponse(BaseModel):
    success: bool
    coupon_code: str
    order_id: str
    discount_amount: float
    message: str
    status: str
    is_replay: bool = False
