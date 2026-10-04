import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Index, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customers.id"))
    order_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("orders.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(500))
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    escalation_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    assigned_to: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    coupon_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    coupon_discount: Mapped[Optional[float]] = mapped_column(Float, default=0.0, nullable=True)
    coupon_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    coupon_abuse_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    close_reason: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customer: Mapped["Customer"] = relationship()
    order: Mapped[Optional["Order"]] = relationship()
    assignee: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to])
    messages: Mapped[List["Message"]] = relationship(back_populates="ticket")
    internal_notes: Mapped[List["TicketNote"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")
    runs: Mapped[List["Run"]] = relationship(back_populates="ticket")
    drafts: Mapped[List["Draft"]] = relationship(back_populates="ticket")
    actions: Mapped[List["ToolAction"]] = relationship(back_populates="ticket")

    @property
    def computed_assignee_name(self) -> Optional[str]:
        assignee_obj = getattr(self, "__dict__", {}).get("assignee")
        if assignee_obj:
            return getattr(assignee_obj, "name", None) or getattr(assignee_obj, "username", None)
        return None

    __table_args__ = (
        Index("ix_tickets_status_created_at", "status", "created_at"),
        Index("ix_tickets_customer_id", "customer_id"),
        Index("ix_tickets_order_id", "order_id"),
        Index("ix_tickets_risk_level", "risk_level"),
    )
