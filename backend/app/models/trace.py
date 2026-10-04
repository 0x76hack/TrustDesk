import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class Trace(Base):
    __tablename__ = 'traces'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('tickets.id'), nullable=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey('runs.id'))
    run_type: Mapped[str] = mapped_column(String(20))
    retrieved_doc_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_actions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_factors: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    guardrail_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_status: Mapped[str] = mapped_column(String(20))
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["Run"] = relationship(back_populates="traces")

    __table_args__ = (
        Index('ix_traces_ticket_id_created_at', 'ticket_id', 'created_at'),
    )
