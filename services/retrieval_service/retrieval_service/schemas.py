from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RetrievalFilters(BaseModel):
    product: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[List[str]] = None
    doc_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None


class RetrievalQuery(BaseModel):
    query: str
    tenant_id: str
    max_results: Optional[int] = None
    filters: Optional[RetrievalFilters] = None
    doc_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None


class RetrievalHit(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    chunk_id: Optional[str] = None
    text: str
    score: float
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class RetrievalResponse(BaseModel):
    hits: List[RetrievalHit] = Field(default_factory=list)
