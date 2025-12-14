from fastapi import FastAPI

from retrieval_service.config import get_settings
from retrieval_service.logging import configure_logging
from retrieval_service.routers import retrieval
from retrieval_service.routers import chunks
from retrieval_service.core.index import InMemoryIndex, ChromaIndex, chromadb
from retrieval_service.core.embedding import EmbeddingClient
from retrieval_service.core.reranker import SectionReranker

settings = get_settings()
configure_logging(settings.log_level)


def build_index():
    if settings.mock_mode:
        return InMemoryIndex()
    if settings.vector_backend.lower() == "chroma":
        if chromadb is None:
            raise RuntimeError("chromadb is not installed")
        client = (
            chromadb.HttpClient(host=settings.chroma_host)  # type: ignore[arg-type]
            if settings.chroma_host
            else chromadb.PersistentClient(path=settings.chroma_path)
        )
        embedding = EmbeddingClient(settings)
        return ChromaIndex(
            client=client,
            collection_name=settings.chroma_collection,
            embedding=embedding,
            max_results=settings.max_results,
            topk_per_doc=settings.topk_per_doc,
            min_score=settings.min_score,
            reranker=SectionReranker(settings),
            doc_top_k=settings.doc_top_k,
            section_top_k=settings.section_top_k,
            chunk_top_k=settings.chunk_top_k,
            min_docs=getattr(settings, "min_docs", settings.doc_top_k),
        )
    raise RuntimeError(f"Unsupported vector backend: {settings.vector_backend}")


app = FastAPI(title=settings.app_name)
app.state.index = build_index()
app.state.settings = settings
app.include_router(retrieval.router)
app.include_router(chunks.router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    status = {"status": "ok"}
    if not settings.mock_mode and settings.vector_backend.lower() == "chroma":
        status["backend"] = "chroma"
        try:
            # ping collection
            _ = app.state.index.collection.count()  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - runtime path
            status["status"] = "degraded"
            status["error"] = str(exc)
    return status
