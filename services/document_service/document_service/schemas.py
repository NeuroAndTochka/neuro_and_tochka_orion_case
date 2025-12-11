from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentSection(BaseModel):
    section_id: str
    title: str
    page_start: int
    page_end: int
    chunk_ids: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    storage_path: Optional[str] = None


class DocumentDetail(BaseModel):
    doc_id: str
    name: str
    tenant_id: str
    status: str
    product: Optional[str] = None
    version: Optional[str] = None
    storage_uri: Optional[str] = None
    pages: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    sections: List[DocumentSection] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DocumentItem(BaseModel):
    doc_id: str
    name: str
    status: str
    product: Optional[str] = None
    version: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    updated_at: datetime


class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentItem]


class DocumentCreateRequest(BaseModel):
    doc_id: str
    tenant_id: str
    name: str
    product: Optional[str] = None
    version: Optional[str] = None
    status: str = "uploaded"
    storage_uri: Optional[str] = None
    pages: Optional[int] = None
    tags: List[str] = Field(default_factory=list)


class SectionUpsertItem(BaseModel):
    section_id: str
    title: str
    page_start: int
    page_end: int
    chunk_ids: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    storage_path: Optional[str] = None


class SectionsUpsertRequest(BaseModel):
    sections: List[SectionUpsertItem]


class StatusUpdateRequest(BaseModel):
    doc_id: str
    status: str
    error: Optional[str] = None
    storage_uri: Optional[str] = None
    pages: Optional[int] = None


class DownloadUrlResponse(BaseModel):
    doc_id: str
    url: str
    expires_in: int


DocumentDetail.model_rebuild()
