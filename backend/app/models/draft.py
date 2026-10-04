import uuid
from datetime import datetime
from typing import List
from sqlalchemy import String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base

class Draft(Base):
    __tablename__ = 'drafts'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey('tickets.id'))
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('runs.id', ondelete='SET NULL'), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    ticket: Mapped["Ticket"] = relationship(back_populates="drafts")
    run: Mapped["Run"] = relationship()
    citations: Mapped[List["Citation"]] = relationship(back_populates="draft")

class Citation(Base):
    __tablename__ = 'citations'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey('drafts.id'))
    doc_id: Mapped[str] = mapped_column(String(50), ForeignKey('kb_documents.doc_id'))
    chunk_id: Mapped[str | None] = mapped_column(String(36), ForeignKey('kb_chunks.id'), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float)
    
    draft: Mapped["Draft"] = relationship(back_populates="citations")
