import uuid
from datetime import datetime
from typing import List
from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class EvalRun(Base):
    __tablename__ = 'eval_runs'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(20))
    summary_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    results: Mapped[List["EvalResult"]] = relationship(back_populates="run")

class EvalResult(Base):
    __tablename__ = 'eval_results'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    eval_run_id: Mapped[str] = mapped_column(String(36), ForeignKey('eval_runs.id'))
    case_id: Mapped[str] = mapped_column(String(50))
    expected: Mapped[dict] = mapped_column(JSON)
    observed: Mapped[dict] = mapped_column(JSON)
    triage_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    citation_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    unsafe_block_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    escalation_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    run: Mapped["EvalRun"] = relationship(back_populates="results")
