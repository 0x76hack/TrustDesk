import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class Message(Base):
    __tablename__ = 'messages'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey('tickets.id'))
    sender_type: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")

    __table_args__ = (
        Index('ix_messages_ticket_id_created_at', 'ticket_id', 'created_at'),
    )
