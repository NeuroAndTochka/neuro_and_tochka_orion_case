from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class IngestionTicket(BaseModel):
    job_id: str
    doc_id: str
    status: str
    submitted_at: datetime


class EnqueueResponse(BaseModel):
    job_id: str
    doc_id: str
    status: str


class StatusPayload(BaseModel):
    job_id: str
    doc_id: str
    status: str
    error: Optional[str] = None
    chunk_ids: Optional[List[str]] = None
