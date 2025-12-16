import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from retrieval_service.config import Settings

router = APIRouter(prefix="/internal/retrieval/chunks", tags=["chunks"])
logger = structlog.get_logger(__name__)


def get_state(request: Request):
    index = getattr(request.app.state, "index", None)
    settings = getattr(request.app.state, "settings", None)
    if index is None or settings is None:
        raise RuntimeError("Service not initialized")
    return index, settings


@router.post("/window")
async def chunk_window(
    payload: dict,
    request: Request,
):
    index, settings = get_state(request)
    tenant_id = payload.get("tenant_id")
    doc_id = payload.get("doc_id")
    anchor_id = payload.get("anchor_chunk_id")
    before = int(payload.get("window_before") or 1)
    after = int(payload.get("window_after") or 1)
    if not tenant_id or not doc_id or not anchor_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id, doc_id, anchor_chunk_id required")
    logger.info(
        "chunk_window_request",
        tenant_id=tenant_id,
        doc_id=doc_id,
        anchor_chunk_id=anchor_id,
        window_before=before,
        window_after=after,
    )
    records = []
    collection = getattr(index, "collection", None)
    if collection:
        try:
            include = ["metadatas"]
            logger.info(
                "chunk_window_chroma_get",
                tenant_id=tenant_id,
                doc_id=doc_id,
                include=include,
                limit=1000,
            )
            chunks = collection.get(  # type: ignore[attr-defined]
                where={"$and": [{"tenant_id": tenant_id}, {"doc_id": doc_id}]},
                include=include,
                limit=1000,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        ids = chunks.get("ids") or []
        metas = chunks.get("metadatas") or []
        for cid, meta in zip(ids, metas):
            if not meta:
                continue
            chunk_id = meta.get("chunk_id") or cid
            page = meta.get("page")
            idx = meta.get("chunk_index")
            text = meta.get("text") or ""
            records.append({"chunk_id": chunk_id, "page": page, "chunk_index": idx, "text": text})
        logger.info(
            "chunk_window_retrieved_from_chroma",
            doc_id=doc_id,
            count=len(records),
        )
    else:
        docs = getattr(index, "documents", None)
        if docs:
            filtered = [d for d in docs if getattr(d, "doc_id", None) == doc_id]
            for pos, hit in enumerate(filtered):
                records.append(
                    {
                        "chunk_id": getattr(hit, "chunk_id", None) or getattr(hit, "section_id", None) or f"chunk_{pos}",
                        "page": getattr(hit, "page_start", None) or getattr(hit, "page", None),
                        "chunk_index": getattr(hit, "chunk_index", None) or pos,
                        "text": getattr(hit, "text", "") or "",
                    }
                )
        logger.info(
            "chunk_window_retrieved_from_memory",
            doc_id=doc_id,
            count=len(records),
        )
    if not records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chunks_not_found")
    records.sort(key=lambda r: (r.get("page") or 0, r.get("chunk_index") or 0))
    anchor_pos = next((i for i, r in enumerate(records) if r["chunk_id"] == anchor_id), None)
    if anchor_pos is None:
        raise HTTPException(status_code=404, detail="anchor_chunk_not_found")
    start = max(0, anchor_pos - before)
    end = min(len(records), anchor_pos + after + 1)
    window = records[start:end]
    logger.info(
        "chunk_window_response",
        doc_id=doc_id,
        anchor_chunk_id=anchor_id,
        returned=len(window),
    )
    return {"chunks": window}
