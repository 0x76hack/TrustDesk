from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DraftRequest(BaseModel):
    tone: str = "professional"


class DraftResponse(BaseModel):
    run_id: str


class CitationResponse(BaseModel):
    id: str
    doc_id: str
    chunk_id: Optional[str] = None
    relevance_score: Optional[float] = None

    model_config = {"from_attributes": True}


class DraftDetailResponse(BaseModel):
    id: str
    ticket_id: str
    run_id: str
    body: str
    status: str
    citations: List[CitationResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
