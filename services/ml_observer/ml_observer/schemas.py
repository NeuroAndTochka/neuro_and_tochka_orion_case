from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExperimentCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)


class ExperimentRunSummary(BaseModel):
    run_id: str
    run_type: str
    status: str
    created_at: datetime
    metrics: Dict[str, Any] = Field(default_factory=dict)
    result: Dict[str, Any] = Field(default_factory=dict)


class ExperimentDetail(BaseModel):
    experiment_id: str
    name: str
    description: Optional[str] = None
    tenant_id: str
    status: str
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    runs: List[ExperimentRunSummary] = Field(default_factory=list)


class DocumentUploadRequest(BaseModel):
    doc_id: str
    name: Optional[str] = None
    storage_uri: Optional[str] = None
    experiment_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class DocumentStatus(BaseModel):
    doc_id: str
    status: str
    storage_uri: Optional[str] = None
    experiment_id: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class RetrievalRunRequest(BaseModel):
    queries: List[str]
    top_k: int = 5
    filters: Dict[str, Any] = Field(default_factory=dict)
    rerank: Dict[str, Any] = Field(default_factory=dict)
    experiment_id: Optional[str] = None


class RetrievalSearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None
    doc_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None
    trace_id: Optional[str] = None
    rerank_enabled: Optional[bool] = None


class RetrievalHit(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    score: float
    chunk_id: Optional[str] = None
    snippet: Optional[str] = None


class RetrievalRunResponse(BaseModel):
    run_id: str
    status: str
    hits: List[RetrievalHit]
    metrics: Dict[str, Any] = Field(default_factory=dict)


class LLMDryRunRequest(BaseModel):
    prompt: str
    context: List[str] = Field(default_factory=list)
    experiment_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMDryRunResponse(BaseModel):
    run_id: str
    status: str
    answer: str
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
