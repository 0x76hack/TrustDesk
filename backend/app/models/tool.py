import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class ToolDefinition(Base):
    __tablename__ = 'tool_definitions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=True)
    parameter_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class ToolAction(Base):
    __tablename__ = 'tool_actions'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey('tickets.id'))
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('runs.id'), nullable=True)
    tool_id: Mapped[str] = mapped_column(String(36), ForeignKey('tool_definitions.id'))
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    proposed_by_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('users.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tool: Mapped["ToolDefinition"] = relationship()
    ticket: Mapped["Ticket"] = relationship(back_populates="actions")
    approval: Mapped["Approval"] = relationship(back_populates="action")

    __table_args__ = (
        Index('ix_tool_actions_idempotency_key', 'idempotency_key', unique=True),
        Index('ix_tool_actions_ticket_id', 'ticket_id'),
    )
