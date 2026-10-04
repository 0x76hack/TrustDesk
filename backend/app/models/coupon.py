import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

if TYPE_CHECKING:
    from .customer import Customer
    from .order import Order
    from .ticket import Ticket


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"), index=True)
    original_order_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)
    ticket_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tickets.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    status: Mapped[str] = mapped_column(String(30), default="active")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(200), unique=True, nullable=True)
    redeemed_order_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)
    redeemed_ticket_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tickets.id"), nullable=True)
    redeemed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(foreign_keys=[customer_id])
    original_order: Mapped[Optional["Order"]] = relationship(foreign_keys=[original_order_id])
    redeemed_order: Mapped[Optional["Order"]] = relationship(foreign_keys=[redeemed_order_id])

    __table_args__ = (
        Index("ix_coupons_customer_status", "customer_id", "status"),
        Index("ix_coupons_code_status", "code", "status"),
    )
