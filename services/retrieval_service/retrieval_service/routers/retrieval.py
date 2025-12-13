from fastapi import APIRouter, Depends, HTTPException, Request, status

from retrieval_service.core.index import InMemoryIndex
from retrieval_service.schemas import RetrievalQuery, RetrievalResponse
from retrieval_service.config import Settings

router = APIRouter(prefix="/internal/retrieval", tags=["retrieval"])


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
async def search(query: RetrievalQuery, index=Depends(get_index), settings: Settings = Depends(get_settings)) -> RetrievalResponse:
    requested = query.max_results or settings.max_results
    max_cap = max(1, settings.max_results)
    query.max_results = min(requested, max_cap, 50)
    try:
        hits = index.search(query)
        return RetrievalResponse(hits=hits)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "backend_unavailable", "message": str(exc)},
        )
