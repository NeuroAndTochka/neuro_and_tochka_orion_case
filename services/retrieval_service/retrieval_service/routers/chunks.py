from fastapi import APIRouter, Depends, HTTPException, Request, status

from retrieval_service.config import Settings

router = APIRouter(prefix="/internal/retrieval/chunks", tags=["chunks"])


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
    try:
        chunks = index.collection.get(  # type: ignore[attr-defined]
            where={"$and": [{"tenant_id": tenant_id}, {"doc_id": doc_id}]},
            include=["metadatas", "ids"],
            limit=1000,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    ids = chunks.get("ids") or []
    metas = chunks.get("metadatas") or []
    records = []
    for cid, meta in zip(ids, metas):
        if not meta:
            continue
        chunk_id = meta.get("chunk_id") or cid
        page = meta.get("page")
        idx = meta.get("chunk_index")
        text = meta.get("text") or ""
        records.append({"chunk_id": chunk_id, "page": page, "chunk_index": idx, "text": text})
    records.sort(key=lambda r: (r.get("page") or 0, r.get("chunk_index") or 0))
    anchor_pos = next((i for i, r in enumerate(records) if r["chunk_id"] == anchor_id), None)
    if anchor_pos is None:
        raise HTTPException(status_code=404, detail="anchor_chunk_not_found")
    start = max(0, anchor_pos - before)
    end = min(len(records), anchor_pos + after + 1)
    return {"chunks": records[start:end]}
