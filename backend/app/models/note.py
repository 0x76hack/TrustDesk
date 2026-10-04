import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class TicketNote(Base):
    __tablename__ = "ticket_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"))
    author_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="internal_notes")
    author: Mapped["User"] = relationship()

    __table_args__ = (
        Index("ix_ticket_notes_ticket_id_created_at", "ticket_id", "created_at"),
    )
