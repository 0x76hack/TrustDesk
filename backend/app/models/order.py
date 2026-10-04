import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Float, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

if TYPE_CHECKING:
    from .customer import Customer

class Order(Base):
    __tablename__ = 'orders'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey('customers.id'))
    restaurant: Mapped[str] = mapped_column(String(200))
    restaurant_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(50))
    live_status_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    delivery_partner_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_partner_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delay_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), default="UPI", nullable=True)
    total: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default='INR')
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = 'order_items'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey('orders.id'))
    item_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
