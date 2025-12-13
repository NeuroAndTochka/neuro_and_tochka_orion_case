from __future__ import annotations

from __future__ import annotations

from typing import Iterable, List, Optional

import structlog

from retrieval_service.core.embedding import EmbeddingClient
from retrieval_service.schemas import RetrievalHit, RetrievalQuery

try:  # pragma: no cover - optional dependency
    import chromadb  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    chromadb = None  # type: ignore


class InMemoryIndex:
    def __init__(self) -> None:
        self.documents = [
            RetrievalHit(
                doc_id="doc_1",
                section_id="sec_intro",
                chunk_id="chunk_1",
                text="LDAP integration introduction",
                score=0.98,
                page_start=1,
                page_end=2,
            ),
            RetrievalHit(
                doc_id="doc_1",
                section_id="sec_setup",
                chunk_id="chunk_2",
                text="Step-by-step setup",
                score=0.85,
                page_start=3,
                page_end=5,
            ),
        ]

    def search(self, query: RetrievalQuery) -> List[RetrievalHit]:
        q = query.query.lower()
        results = [hit for hit in self.documents if q in hit.text.lower() and (not query.doc_ids or hit.doc_id in (query.doc_ids or []))]
        return results[: query.max_results or len(results)]


class ChromaIndex:
    def __init__(self, client, collection_name: str, embedding: EmbeddingClient, max_results: int, topk_per_doc: int = 0, min_score: float | None = None) -> None:
        self.client = client
        self.collection = client.get_or_create_collection(collection_name)
        self.embedding = embedding
        self.max_results = max_results
        self.topk_per_doc = topk_per_doc
        self.min_score = min_score
        self._logger = structlog.get_logger(__name__)

    def _build_where(self, query: RetrievalQuery) -> dict:
        where = {"tenant_id": query.tenant_id}
        if query.doc_ids:
            where["doc_id"] = {"$in": query.doc_ids}
        if query.section_ids:
            where["section_id"] = {"$in": query.section_ids}
        if query.filters:
            if query.filters.product:
                where["product"] = query.filters.product
            if query.filters.version:
                where["version"] = query.filters.version
            if query.filters.tags:
                where["tags"] = {"$in": query.filters.tags}
        return where

    def search(self, query: RetrievalQuery) -> List[RetrievalHit]:
        where = self._build_where(query)
        max_results = query.max_results or self.max_results
        query_embedding = self.embedding.embed([query.query])[0]
        n_results = max_results * 3 if self.topk_per_doc else max_results
        res = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["metadatas", "distances", "documents"],
        )
        ids = res.get("ids", [[]])[0] if res else []
        metas = res.get("metadatas", [[]])[0] if res else []
        distances = res.get("distances", [[]])[0] if res else []
        hits = []
        for cid, meta, dist in zip(ids, metas, distances):
            if not meta:
                continue
            score = 1 - dist if dist is not None else 0.0
            if self.min_score is not None and score < self.min_score:
                continue
            hit = RetrievalHit(
                doc_id=meta.get("doc_id", ""),
                section_id=meta.get("section_id"),
                chunk_id=meta.get("chunk_id") or cid,
                text=meta.get("text") or "",
                score=score,
                page_start=meta.get("page_start"),
                page_end=meta.get("page_end"),
            )
            hits.append(hit)

        # enforce per-doc limit and max_results
        limited = []
        per_doc_counts: dict[str, int] = {}
        for hit in sorted(hits, key=lambda h: h.score, reverse=True):
            count = per_doc_counts.get(hit.doc_id, 0)
            if self.topk_per_doc and count >= self.topk_per_doc:
                continue
            per_doc_counts[hit.doc_id] = count + 1
            limited.append(hit)
            if len(limited) >= max_results:
                break
        self._logger.info(
            "retrieval_chroma_results",
            tenant_id=query.tenant_id,
            hits=len(limited),
            requested=max_results,
            total_raw=len(hits),
        )
        return limited
