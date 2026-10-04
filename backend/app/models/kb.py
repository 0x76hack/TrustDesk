import uuid
from datetime import datetime
from typing import List, Any
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from ..database import Base

class KBDocument(Base):
    __tablename__ = 'kb_documents'

    doc_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_adversarial: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[List["KBChunk"]] = relationship(back_populates="document")

class KBChunk(Base):
    __tablename__ = 'kb_chunks'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(String(50), ForeignKey('kb_documents.doc_id'))
    chunk_seq: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(768))
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    document: Mapped["KBDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index('ix_kb_chunks_embedding', 'embedding', postgresql_using='hnsw', postgresql_with={'m': 16, 'ef_construction': 64}, postgresql_ops={'embedding': 'vector_cosine_ops'}),
        Index('ix_kb_chunks_doc_id', 'doc_id'),
    )
