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
    docs_top_k: Optional[int] = None
    sections_top_k_per_doc: Optional[int] = None
    max_total_sections: Optional[int] = None
    rerank_score_threshold: Optional[float] = None
    enable_section_cosine: Optional[bool] = None
    enable_rerank: Optional[bool] = None
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


class LLMConfig(BaseModel):
    default_model: Optional[str] = None
    max_tool_steps: Optional[int] = None
    enable_json_mode: Optional[bool] = None
    mock_mode: Optional[bool] = None
    llm_runtime_url: Optional[str] = None


class LLMDryRunResponse(BaseModel):
    run_id: str
    status: str
    answer: str
    usage: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestratorRequest(BaseModel):
    query: str
    max_results: Optional[int] = None
    doc_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    user: Optional[Dict[str, Any]] = None
    tenant_id: Optional[str] = None
    docs_top_k: Optional[int] = None
    sections_top_k_per_doc: Optional[int] = None
    max_total_sections: Optional[int] = None
    rerank_score_threshold: Optional[float] = None
    enable_section_cosine: Optional[bool] = None
    enable_rerank: Optional[bool] = None
    rerank_enabled: Optional[bool] = None


class OrchestratorConfig(BaseModel):
    default_model: Optional[str] = None
    model_strategy: Optional[str] = None
    prompt_token_budget: Optional[int] = None
    context_token_budget: Optional[int] = None
    max_tool_steps: Optional[int] = None
    window_radius: Optional[int] = None
    window_initial: Optional[int] = None
    window_step: Optional[int] = None
    window_max: Optional[int] = None
    mock_mode: Optional[bool] = None
