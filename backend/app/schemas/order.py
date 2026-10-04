from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class OrderItemCreate(BaseModel):
    item_name: str
    quantity: int = Field(gt=0)
    unit_price: float = Field(ge=0)


class OrderItemResponse(BaseModel):
    id: str
    item_name: str
    quantity: int
    unit_price: float

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    customer_id: str
    restaurant: str
    restaurant_address: Optional[str] = None
    delivery_address: Optional[str] = None
    status: str = "placed"
    live_status_message: Optional[str] = None
    delivery_partner_name: Optional[str] = None
    delivery_partner_phone: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None
    delay_reason: Optional[str] = None
    payment_method: Optional[str] = "UPI"
    total: float
    currency: str = "INR"
    placed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items: List[OrderItemCreate] = Field(default_factory=list)


class OrderResponse(BaseModel):
    id: str
    customer_id: str
    restaurant: str
    restaurant_address: Optional[str] = None
    delivery_address: Optional[str] = None
    status: str
    live_status_message: Optional[str] = None
    delivery_partner_name: Optional[str] = None
    delivery_partner_phone: Optional[str] = None
    estimated_delivery_at: Optional[datetime] = None
    delay_reason: Optional[str] = None
    payment_method: Optional[str] = "UPI"
    total: float
    currency: str
    coupon_code: Optional[str] = None
    discount_amount: Optional[float] = 0.0
    placed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    items: List[OrderItemResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
