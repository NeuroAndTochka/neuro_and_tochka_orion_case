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
    enable_filters: Optional[bool] = None
    rerank_enabled: Optional[bool] = None


class RetrievalStepResults(BaseModel):
    docs: List[RetrievalHit] = Field(default_factory=list)
    sections: List[RetrievalHit] = Field(default_factory=list)
    chunks: List[RetrievalHit] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    chunk_id: Optional[str] = None
    text: str
    score: float
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    chunk_ids: Optional[List[str]] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    page: Optional[int] = None
    chunk_index: Optional[int] = None


class RetrievalResponse(BaseModel):
    hits: List[RetrievalHit] = Field(default_factory=list)
    steps: Optional[RetrievalStepResults] = None
