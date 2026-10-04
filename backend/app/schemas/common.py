from pydantic import BaseModel, Field
from typing import Optional, Any, List, Generic, TypeVar
from datetime import datetime

T = TypeVar('T')

class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    limit: int
    offset: int
