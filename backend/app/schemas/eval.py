from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class EvalResultResponse(BaseModel):
    id: str
    eval_run_id: str
    case_id: str
    expected: Dict[str, Any] = Field(default_factory=dict)
    observed: Dict[str, Any] = Field(default_factory=dict)
    triage_pass: Optional[bool] = None
    citation_pass: Optional[bool] = None
    unsafe_block_pass: Optional[bool] = None
    escalation_pass: Optional[bool] = None

    model_config = {"from_attributes": True}


class EvalRunResponse(BaseModel):
    id: str
    status: str
    summary_metrics: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EvalRunDetailResponse(EvalRunResponse):
    results: List[EvalResultResponse] = Field(default_factory=list)
