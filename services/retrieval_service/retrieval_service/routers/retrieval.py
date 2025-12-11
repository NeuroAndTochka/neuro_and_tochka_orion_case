from fastapi import APIRouter, Depends

from retrieval_service.core.index import InMemoryIndex
from retrieval_service.schemas import RetrievalQuery, RetrievalResponse

router = APIRouter(prefix="/internal/retrieval", tags=["retrieval"])


def get_index() -> InMemoryIndex:
    return InMemoryIndex()


@router.post("/search", response_model=RetrievalResponse)
async def search(query: RetrievalQuery, index: InMemoryIndex = Depends(get_index)) -> RetrievalResponse:
    hits = index.search(query)
    return RetrievalResponse(hits=hits)
