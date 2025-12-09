from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MCPUser(BaseModel):
    user_id: str
    tenant_id: str
    roles: Optional[List[str]] = None


class MCPExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    user: MCPUser
    trace_id: Optional[str] = None


class MCPError(BaseModel):
    code: str
    message: str


class MCPExecuteResponse(BaseModel):
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[MCPError] = None
    trace_id: Optional[str] = None


class DocumentSection(BaseModel):
    section_id: str
    title: str
    page_start: int
    page_end: int


class DocumentMetadata(BaseModel):
    doc_id: str
    title: str
    pages: int
    tags: List[str] = Field(default_factory=list)
    sections: List[DocumentSection] = Field(default_factory=list)
    tenant_id: str


class ToolExecutionContext(BaseModel):
    user: MCPUser
    trace_id: str
