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
        "section_top_k": settings.section_top_k,
        "chunk_top_k": settings.chunk_top_k,
        "rerank_enabled": settings.rerank_enabled,
        "rerank_model": settings.rerank_model,
        "rerank_top_n": settings.rerank_top_n,
        "enable_filters": settings.enable_filters,
        "min_docs": settings.min_docs,
    }


@router.post("/config")
async def update_config(payload: dict, settings: Settings = Depends(get_settings)):
    for field in [
        "max_results",
        "topk_per_doc",
        "min_score",
        "doc_top_k",
        "section_top_k",
        "chunk_top_k",
        "rerank_enabled",
        "rerank_model",
        "rerank_top_n",
        "enable_filters",
        "min_docs",
    ]:
        if field in payload and payload[field] is not None:
            setattr(settings, field, payload[field])
    return await get_config(settings)
