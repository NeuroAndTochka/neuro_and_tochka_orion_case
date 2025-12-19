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
    docs_top_k: Optional[int] = None
    sections_top_k_per_doc: Optional[int] = None
    max_total_sections: Optional[int] = None
    rerank_score_threshold: Optional[float] = None
    enable_section_cosine: Optional[bool] = None
    enable_rerank: Optional[bool] = None
    chunks_enabled: Optional[bool] = None
    doc_ids: Optional[List[str]] = None
    section_ids: Optional[List[str]] = None
    enable_filters: Optional[bool] = None
    rerank_enabled: Optional[bool] = None


class RetrievalStepResults(BaseModel):
    docs: List[RetrievalHit] = Field(default_factory=list)
    sections: List[RetrievalHit] = Field(default_factory=list)
    chunks: List[RetrievalHit] = Field(default_factory=list)
    bm25: Optional[List[RetrievalHit]] = None


class RetrievalHit(BaseModel):
    doc_id: str
    section_id: Optional[str] = None
    chunk_id: Optional[str] = None
    text: Optional[str] = Field(default=None, exclude=True)
    score: float
    rerank_score: Optional[float] = None
    bm25_score: Optional[float] = None
    anchor_chunk_id: Optional[str] = None
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
