import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from retrieval_service.core.index import InMemoryIndex  # noqa
from retrieval_service.schemas import RetrievalQuery, RetrievalResponse
from retrieval_service.config import Settings

router = APIRouter(prefix="/internal/retrieval", tags=["retrieval"])
logger = structlog.get_logger(__name__)


def get_index(request: Request):
    index = getattr(request.app.state, "index", None)
    if index is None:
        raise RuntimeError("Index is not initialized")
    return index


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise RuntimeError("Settings not configured")
    return settings


@router.post("/search", response_model=RetrievalResponse)
async def search(
    query: RetrievalQuery,
    index=Depends(get_index),
    settings: Settings = Depends(get_settings),
) -> RetrievalResponse:
    logger.info(
        "retrieval_http_request",
        query=query.query,
        tenant_id=query.tenant_id,
        max_results=query.max_results,
        filters=bool(query.filters),
        doc_ids=bool(query.doc_ids),
        section_ids=bool(query.section_ids),
        trace_id=getattr(query, "trace_id", None),
    )
    index_logger = getattr(index, "_logger", None)
    if index_logger:
        index_logger.info(
            "retrieval_request",
            query=query.query,
            tenant_id=query.tenant_id,
            max_results=query.max_results,
            filters=bool(query.filters),
        )
    requested = query.max_results or settings.max_results
    max_cap = max(1, settings.max_results)
    query.max_results = min(requested, max_cap, 50)
    if query.enable_filters is None:
        query.enable_filters = settings.enable_filters
    query.docs_top_k = max(1, query.docs_top_k or settings.docs_top_k)
    query.sections_top_k_per_doc = max(1, query.sections_top_k_per_doc or settings.sections_top_k_per_doc)
    query.max_total_sections = max(1, query.max_total_sections or settings.max_total_sections)
    if query.enable_section_cosine is None:
        query.enable_section_cosine = settings.enable_section_cosine
    if query.enable_rerank is None:
        query.enable_rerank = query.rerank_enabled if query.rerank_enabled is not None else settings.enable_rerank
    if query.rerank_score_threshold is None:
        query.rerank_score_threshold = settings.rerank_score_threshold
    else:
        query.rerank_score_threshold = min(1.0, max(0.0, query.rerank_score_threshold))
    if query.chunks_enabled is None:
        query.chunks_enabled = settings.chunks_enabled
    try:
        search_result = index.search(query)
        if isinstance(search_result, tuple):
            hits, steps = search_result
        else:
            hits, steps = search_result, None
        if index_logger:
            index_logger.info(
                "retrieval_response",
                tenant_id=query.tenant_id,
                hits=len(hits),
                docs=len(steps.docs) if getattr(steps, "docs", None) else 0,
                sections=len(steps.sections) if getattr(steps, "sections", None) else 0,
                chunks=len(steps.chunks) if getattr(steps, "chunks", None) else 0,
            )
        logger.info(
            "retrieval_http_response",
            hits=len(hits),
            docs=len(steps.docs) if getattr(steps, "docs", None) else 0,
            sections=len(steps.sections) if getattr(steps, "sections", None) else 0,
            chunks=len(steps.chunks) if getattr(steps, "chunks", None) else 0,
            trace_id=getattr(query, "trace_id", None),
        )
        return RetrievalResponse(hits=hits, steps=steps)
    except Exception as exc:
        if index_logger:
            index_logger.error("retrieval_failed", error=str(exc))
        logger.error("retrieval_http_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "backend_unavailable", "message": str(exc)},
        )


@router.get("/config")
async def get_config(settings: Settings = Depends(get_settings)):
    return {
        "max_results": settings.max_results,
        "topk_per_doc": settings.topk_per_doc,
        "min_score": settings.min_score,
        "doc_top_k": settings.doc_top_k,
        "docs_top_k": settings.docs_top_k,
        "section_top_k": settings.section_top_k,
        "sections_top_k_per_doc": settings.sections_top_k_per_doc,
        "max_total_sections": settings.max_total_sections,
        "chunk_top_k": settings.chunk_top_k,
        "rerank_enabled": settings.rerank_enabled,
        "enable_rerank": settings.enable_rerank,
        "rerank_score_threshold": settings.rerank_score_threshold,
        "rerank_model": settings.rerank_model,
        "rerank_top_n": settings.rerank_top_n,
        "enable_filters": settings.enable_filters,
        "enable_section_cosine": settings.enable_section_cosine,
        "chunks_enabled": settings.chunks_enabled,
        "min_docs": settings.min_docs,
        "bm25_enabled": settings.bm25_enabled,
        "bm25_index_path": settings.bm25_index_path,
        "bm25_top_k": settings.bm25_top_k,
        "bm25_weight": settings.bm25_weight,
    }


@router.post("/config")
async def update_config(payload: dict, settings: Settings = Depends(get_settings)):
    for field in [
        "max_results",
        "topk_per_doc",
        "min_score",
        "doc_top_k",
        "docs_top_k",
        "section_top_k",
        "sections_top_k_per_doc",
        "max_total_sections",
        "chunk_top_k",
        "rerank_enabled",
        "enable_rerank",
        "rerank_score_threshold",
        "rerank_model",
        "rerank_top_n",
        "enable_filters",
        "enable_section_cosine",
        "chunks_enabled",
        "min_docs",
        "bm25_enabled",
        "bm25_top_k",
        "bm25_weight",
    ]:
        if field in payload and payload[field] is not None:
            setattr(settings, field, payload[field])
    # keep backward-compatible mirrors
    if payload.get("doc_top_k") is not None or payload.get("docs_top_k") is not None:
        val = payload.get("docs_top_k", payload.get("doc_top_k"))
        if val is not None:
            settings.docs_top_k = max(1, int(val))
    if payload.get("section_top_k") is not None or payload.get("sections_top_k_per_doc") is not None:
        val = payload.get("sections_top_k_per_doc", payload.get("section_top_k"))
        if val is not None:
            settings.sections_top_k_per_doc = max(1, int(val))
    settings.doc_top_k = settings.docs_top_k
    settings.section_top_k = settings.sections_top_k_per_doc
    settings.enable_rerank = settings.enable_rerank if settings.enable_rerank is not None else settings.rerank_enabled
    settings.rerank_enabled = bool(settings.enable_rerank)
    settings.rerank_score_threshold = min(1.0, max(0.0, float(settings.rerank_score_threshold or 0.0)))
    if payload.get("max_total_sections") is not None:
        settings.max_total_sections = max(1, int(payload.get("max_total_sections")))
    settings.max_total_sections = max(1, settings.max_total_sections)
    settings.chunks_enabled = bool(settings.chunks_enabled)
    if payload.get("bm25_top_k") is not None:
        settings.bm25_top_k = max(1, int(payload.get("bm25_top_k")))
    if payload.get("bm25_weight") is not None:
        settings.bm25_weight = min(1.0, max(0.0, float(payload.get("bm25_weight"))))
    return await get_config(settings)
