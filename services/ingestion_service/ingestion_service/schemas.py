from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class IngestionTicket(BaseModel):
    job_id: str
    tenant_id: str
    doc_id: str
    status: str
    submitted_at: datetime
    storage_uri: str | None = None
    error: str | None = None


class EnqueueResponse(BaseModel):
    job_id: str
    tenant_id: str
    doc_id: str
    status: str
    storage_uri: str | None = None


class StatusPayload(BaseModel):
    job_id: str
    status: str
    error: Optional[str] = None
    chunk_ids: Optional[List[str]] = None


class JobStatusResponse(BaseModel):
    job_id: str
    tenant_id: str
    doc_id: str
    status: str
    storage_uri: str | None = None
    error: str | None = None
    logs: List[dict] = []


class SummarizerConfig(BaseModel):
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    max_tokens: Optional[int] = None
    use_roles: Optional[bool] = None


class ChunkingConfig(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
