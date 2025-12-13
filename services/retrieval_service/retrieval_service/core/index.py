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
            RetrievalHit(
                doc_id="doc_2",
                section_id="sec_other",
                chunk_id="chunk_3",
                text="SSO configuration steps",
                score=0.75,
                page_start=1,
                page_end=1,
            ),
        ]

    def search(self, query: RetrievalQuery) -> List[RetrievalHit]:
        q = query.query.lower()
        allowed_docs: Optional[Iterable[str]] = query.doc_ids
        if not allowed_docs and query.filters and query.filters.doc_ids:
            allowed_docs = query.filters.doc_ids
        results = [
            hit
            for hit in self.documents
            if q in hit.text.lower() and (not allowed_docs or hit.doc_id in allowed_docs)
        ]
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
        conditions = [{"tenant_id": query.tenant_id}]
        if query.doc_ids:
            conditions.append({"doc_id": {"$in": query.doc_ids}})
        if query.section_ids:
            conditions.append({"section_id": {"$in": query.section_ids}})
        if query.filters:
            if query.filters.product:
                conditions.append({"product": query.filters.product})
            if query.filters.version:
                conditions.append({"version": query.filters.version})
            if query.filters.tags:
                conditions.append({"tags": {"$in": query.filters.tags}})
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

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
        if not limited:
            limited = self._fallback_metadata_search(query, where, max_results)
        self._logger.info(
            "retrieval_chroma_results",
            tenant_id=query.tenant_id,
            hits=len(limited),
            requested=max_results,
            total_raw=len(hits),
        )
        return limited

    def _fallback_metadata_search(self, query: RetrievalQuery, where: dict, max_results: int) -> List[RetrievalHit]:
        try:
            res = self.collection.get(where=where, include=["metadatas", "ids"], limit=500)
        except Exception as exc:  # pragma: no cover - runtime path
            self._logger.warning("retrieval_fallback_failed", error=str(exc))
            return []
        ids = res.get("ids") or []
        metas = res.get("metadatas") or []
        if not ids or not metas:
            return []
        q = query.query.lower()
        hits: List[RetrievalHit] = []
        for cid, meta in zip(ids, metas):
            if not meta:
                continue
            text = (meta.get("text") or "").lower()
            if q in text:
                hits.append(
                    RetrievalHit(
                        doc_id=meta.get("doc_id", ""),
                        section_id=meta.get("section_id"),
                        chunk_id=meta.get("chunk_id") or cid,
                        text=meta.get("text") or "",
                        score=0.1,
                        page_start=meta.get("page_start"),
                        page_end=meta.get("page_end"),
                    )
                )
        hits = hits[:max_results]
        if hits:
            self._logger.info("retrieval_metadata_fallback_used", hits=len(hits))
        return hits
