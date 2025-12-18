from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


MessageContent = str | List[Dict[str, Any]]


class ChatMessage(BaseModel):
    role: str
    content: MessageContent


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    user: Optional[str] = None
    language: Optional[str] = None


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: Dict[str, Any]
    finish_reason: Optional[str] = "stop"


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None


class AssistantContext(BaseModel):
    channel: Optional[str] = None
    ui_session_id: Optional[str] = None
    conversation_id: Optional[str] = None


class GatewayAssistantRequest(BaseModel):
    query: str
    language: Optional[str] = Field(default=None)
    context: Optional[AssistantContext] = None


class AssistantSource(BaseModel):
    doc_id: str
    doc_title: Optional[str] = None
    section_id: Optional[str] = None
    section_title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class GatewayAssistantResponse(BaseModel):
    answer: str
    sources: List[AssistantSource] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)


class ModelsResponse(BaseModel):
    object: Literal["list"] = "list"
    data: List[Dict[str, str]]
