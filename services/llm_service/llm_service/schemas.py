from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str


class ContextChunk(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    text: str
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class GenerationParams(BaseModel):
    top_p: Optional[float] = 0.95
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    stop: Optional[List[str]] = None


class GenerateRequest(BaseModel):
    mode: str = Field(default="rag")
    system_prompt: str
    messages: List[Message]
    context_chunks: List[ContextChunk] = Field(default_factory=list)
    generation_params: GenerationParams = Field(default_factory=GenerationParams)
    trace_id: Optional[str] = None


class ToolCallTrace(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result_summary: str


class UsageStats(BaseModel):
    prompt: int = 0
    completion: int = 0


class GenerateResponse(BaseModel):
    answer: str
    used_tokens: UsageStats
    tools_called: List[ToolCallTrace] = Field(default_factory=list)
    meta: Dict[str, Any]


class ErrorResponse(BaseModel):
    error: Dict[str, Any]
