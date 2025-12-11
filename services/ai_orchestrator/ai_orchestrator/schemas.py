from __future__ import annotations

from typing import List, Optional

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


class SourceItem(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


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
    safety: SafetyBlock
    telemetry: Telemetry
