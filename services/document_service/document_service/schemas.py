from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentItem(BaseModel):
    doc_id: str
    name: str
    status: str
    product: Optional[str] = None
    version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    updated_at: datetime


class DocumentDetail(BaseModel):
    doc_id: str
    title: str
    pages: int
    tenant_id: str
    tags: List[str] = Field(default_factory=list)
    sections: List["DocumentSection"] = Field(default_factory=list)


class DocumentSection(BaseModel):
    section_id: str
    title: str
    page_start: int
    page_end: int
    chunk_ids: List[str] = Field(default_factory=list)


class StatusUpdateRequest(BaseModel):
    doc_id: str
    status: str
    error: Optional[str] = None


DocumentDetail.model_rebuild()
