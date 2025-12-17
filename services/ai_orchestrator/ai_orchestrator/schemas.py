from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    user_id: str
    tenant_id: str
    roles: List[str] = Field(default_factory=list)


class OrchestratorRequest(BaseModel):
    conversation_id: Optional[str] = None
    user: Optional[UserContext] = None
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    query: str
    channel: Optional[str] = None
    locale: Optional[str] = None
    trace_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    doc_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None
    max_results: Optional[int] = None
    docs_top_k: Optional[int] = None
    sections_top_k_per_doc: Optional[int] = None
    max_total_sections: Optional[int] = None
    rerank_score_threshold: Optional[float] = None
    enable_section_cosine: Optional[bool] = None
    enable_rerank: Optional[bool] = None
    rerank_enabled: Optional[bool] = None


class SourceItem(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    score: Optional[float] = None


class ToolCallTrace(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result_summary: Optional[str] = None


class SafetyBlock(BaseModel):
    input: Optional[str] = None
    output: Optional[str] = None


class Telemetry(BaseModel):
    trace_id: str
    retrieval_latency_ms: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    tool_steps: Optional[int] = None


class OrchestratorResponse(BaseModel):
    answer: str
    sources: List[SourceItem] = Field(default_factory=list)
    tools: List[ToolCallTrace] = Field(default_factory=list)
    safety: SafetyBlock
    telemetry: Telemetry
