from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class KBDocumentCreate(BaseModel):
    doc_id: str
    title: str
    body: str
    category: Optional[str] = "general"
    is_adversarial: bool = False


class KBDocumentResponse(BaseModel):
    doc_id: str
    title: str
    category: Optional[str] = None
    version: int = 1
    is_adversarial: bool = False
    effective_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KBChunkResponse(BaseModel):
    id: str
    doc_id: str
    chunk_seq: int
    content: str
    relevance_score: Optional[float] = None

    model_config = {"from_attributes": True}
