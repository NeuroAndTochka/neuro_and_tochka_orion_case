from __future__ import annotations

from __future__ import annotations

from typing import Iterable, List, Optional, Set

import structlog

from retrieval_service.core.embedding import EmbeddingClient
from retrieval_service.core.reranker import SectionReranker
from retrieval_service.schemas import RetrievalHit, RetrievalQuery, RetrievalStepResults

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
                summary="LDAP integration introduction",
                score=0.98,
                page_start=1,
                page_end=2,
            ),
            RetrievalHit(
                doc_id="doc_1",
                section_id="sec_setup",
                chunk_id="chunk_2",
                text="Step-by-step setup",
                summary="Step-by-step setup",
                score=0.85,
                page_start=3,
                page_end=5,
            ),
            RetrievalHit(
                doc_id="doc_2",
                section_id="sec_other",
                chunk_id="chunk_3",
                text="SSO configuration steps",
                summary="SSO configuration steps",
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
        for hit in results:
            if hit.chunk_id and not hit.anchor_chunk_id:
                hit.anchor_chunk_id = hit.chunk_id
        return results[: query.max_results or len(results)]


class ChromaIndex:
    def __init__(
        self,
        client,
        collection_name: str,
        embedding: EmbeddingClient,
        max_results: int,
        topk_per_doc: int = 0,
        doc_collection: str = "ingestion_docs",
        section_collection: str = "ingestion_sections",
        reranker: SectionReranker | None = None,
        doc_top_k: int = 5,
        docs_top_k: int | None = None,
        section_top_k: int = 10,
        sections_top_k_per_doc: int | None = None,
        max_total_sections: int | None = None,
        chunk_top_k: int = 20,
        min_docs: int = 0,
        enable_section_cosine: bool = True,
        enable_rerank: bool | None = None,
        rerank_score_threshold: float = 0.0,
        chunks_enabled: bool = False,
    ) -> None:
        self.client = client
        self.collection = client.get_or_create_collection(collection_name)
        self.doc_collection = client.get_or_create_collection(doc_collection)
        self.section_collection = client.get_or_create_collection(section_collection)
        self.embedding = embedding
        self.max_results = max_results
        self.topk_per_doc = topk_per_doc
        self.min_score = None
        self.doc_top_k = docs_top_k or doc_top_k
        self.section_top_k = sections_top_k_per_doc or section_top_k
        self.max_total_sections = max_total_sections or self.section_top_k
        self.chunk_top_k = chunk_top_k
        self.reranker = reranker
        self.enable_section_cosine = enable_section_cosine
        self.enable_rerank = enable_rerank
        self.rerank_score_threshold = rerank_score_threshold
        self.chunks_enabled = chunks_enabled
        self.min_docs = min_docs or doc_top_k
        self._logger = structlog.get_logger(__name__)

    def _build_where(self, query: RetrievalQuery) -> dict:
        conditions = [{"tenant_id": query.tenant_id}]
        if query.enable_filters is False:
            return conditions[0]
        if query.section_ids:
            conditions.append({"section_id": {"$in": query.section_ids}})
        if query.filters:
            if query.filters.product:
                conditions.append({"product": query.filters.product})
            if query.filters.version:
                conditions.append({"version": query.filters.version})
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def search(self, query: RetrievalQuery) -> tuple[List[RetrievalHit], RetrievalStepResults]:
        where = self._build_where(query)
        max_results = query.max_results or self.max_results
        docs_top_k = max(1, query.docs_top_k or self.doc_top_k)
        sections_top_k = max(1, query.sections_top_k_per_doc or self.section_top_k)
        max_total_sections = query.max_total_sections or self.max_total_sections or sections_top_k
        max_sections_cap = min(max_total_sections, max_results) if max_total_sections else max_results
        section_cosine_enabled = (
            query.enable_section_cosine if query.enable_section_cosine is not None else self.enable_section_cosine
        )
        chunks_enabled = self.chunks_enabled if query.chunks_enabled is None else bool(query.chunks_enabled)
        rerank_threshold = query.rerank_score_threshold
        if rerank_threshold is None:
            rerank_threshold = self.rerank_score_threshold
        rerank_threshold = min(1.0, max(0.0, float(rerank_threshold or 0.0)))
        use_rerank = False
        if self.reranker and self.reranker.available():
            if query.enable_rerank is not None:
                use_rerank = query.enable_rerank
            elif query.rerank_enabled is not None:
                use_rerank = query.rerank_enabled
            elif self.enable_rerank is not None:
                use_rerank = self.enable_rerank
            else:
                use_rerank = bool(self.reranker.settings.rerank_enabled)

        self._logger.info(
            "retrieval_parameters_resolved",
            docs_top_k=docs_top_k,
            sections_top_k_per_doc=sections_top_k,
            max_total_sections=max_total_sections,
            max_sections_cap=max_sections_cap,
            rerank_threshold=rerank_threshold,
            section_cosine_enabled=section_cosine_enabled,
            rerank_enabled=use_rerank,
            chunks_enabled=chunks_enabled,
            max_results=max_results,
            chunk_top_k=self.chunk_top_k,
            topk_per_doc=self.topk_per_doc,
            min_docs=self.min_docs,
        )

        query_embedding = self.embedding.embed([query.query])[0]
        steps = RetrievalStepResults()
        tags_filter: Set[str] | None = None
        if query.filters and query.filters.tags:
            tags_filter = {t.lower() for t in query.filters.tags if t}

        # Doc-level
        self._logger.info(
            "retrieval_stage_start",
            stage="docs",
            collection=getattr(self.doc_collection, "name", "ingestion_docs"),
            where=where,
            requested=docs_top_k,
        )
        doc_hits = self._search_collection(
            self.doc_collection, query_embedding, where, docs_top_k, is_doc=True, tags_filter=tags_filter
        )
        steps.docs = doc_hits
        doc_ids = [h.doc_id for h in doc_hits] if doc_hits else []
        if len(doc_hits) < self.min_docs:
            padded = self._pad_docs_with_metadata(where, doc_ids, self.min_docs - len(doc_hits), tags_filter=tags_filter)
            if padded:
                doc_hits.extend(padded)
                steps.docs = doc_hits
                doc_ids.extend([d.doc_id for d in padded if d.doc_id])
        self._logger.info(
            "retrieval_doc_cosine_ordering",
            ordering=[{"doc_id": d.doc_id, "score": d.score} for d in doc_hits],
        )
        self._logger.info(
            "retrieval_stage_result",
            stage="docs",
            returned=len(doc_hits),
            doc_ids=[d.doc_id for d in doc_hits],
        )
        if not doc_hits:
            self._log_metadata_keys(self.doc_collection, where, stage="docs", tags_filter=tags_filter)

        # Section-level
        section_hits: List[RetrievalHit] = []
        section_logs: List[dict] = []
        if section_cosine_enabled and doc_ids:
            self._logger.info(
                "retrieval_stage_start",
                stage="sections",
                collection=getattr(self.section_collection, "name", "ingestion_sections"),
                where=where,
                requested=sections_top_k,
                per_doc=len(doc_ids),
            )
            doc_score_map = {d.doc_id: d.score for d in doc_hits}
            for doc_id in doc_ids:
                doc_clause = {"doc_id": {"$in": [doc_id]}}
                if "$and" in where:
                    section_where = {"$and": [*where.get("$and", []), doc_clause]}
                else:
                    section_where = {"$and": [where, doc_clause]}
                per_doc_hits = self._search_collection(
                    self.section_collection,
                    query_embedding,
                    section_where,
                    sections_top_k,
                    is_section=True,
                    tags_filter=tags_filter,
                )
                section_hits.extend(per_doc_hits)
                section_logs.append(
                    {
                        "doc_id": doc_id,
                        "sections": [{"section_id": h.section_id, "score": h.score} for h in per_doc_hits],
                    }
                )
            self._logger.info("retrieval_section_cosine_ordering", per_doc=section_logs)
            section_hits.sort(key=lambda h: (doc_score_map.get(h.doc_id, 0.0), h.score), reverse=True)
            if max_sections_cap:
                section_hits = section_hits[:max_sections_cap]

        reranked_sections = section_hits
        rerank_snapshot = section_hits
        if use_rerank and section_hits:
            top_n = min(self.reranker.settings.rerank_top_n, max_sections_cap) if max_sections_cap else self.reranker.settings.rerank_top_n
            reranked_sections = self.reranker.rerank(query.query, section_hits, top_n=top_n)
            rerank_snapshot = reranked_sections
            self._logger.info(
                "retrieval_rerank_scores",
                scores=[
                    {
                        "doc_id": hit.doc_id,
                        "section_id": hit.section_id,
                        "rerank_score": hit.rerank_score if hit.rerank_score is not None else hit.score,
                    }
                    for hit in reranked_sections
                ],
                threshold=rerank_threshold,
            )
            if rerank_threshold:
                before = len(reranked_sections)
                reranked_sections = [
                    hit for hit in reranked_sections if (hit.rerank_score if hit.rerank_score is not None else hit.score) >= rerank_threshold
                ]
                dropped = before - len(reranked_sections)
                self._logger.info(
                    "retrieval_rerank_threshold_applied",
                    threshold=rerank_threshold,
                    dropped=dropped,
                    kept=len(reranked_sections),
                )
        if max_sections_cap and reranked_sections:
            reranked_sections = reranked_sections[:max_sections_cap]
        steps.sections = reranked_sections
        if reranked_sections:
            self._logger.info(
                "retrieval_stage_result",
                stage="sections",
                returned=len(reranked_sections),
            )
        else:
            self._logger.info(
                "retrieval_stage_result",
                stage="sections",
                returned=0,
                reason="section_search_disabled_or_empty" if not section_cosine_enabled else "no_hits",
            )
            if section_cosine_enabled:
                probe_where = {"$and": [where, {"doc_id": {"$in": doc_ids}}]} if doc_ids else where
                self._log_metadata_keys(self.section_collection, probe_where, stage="sections", tags_filter=tags_filter)

        section_ids = [s.section_id for s in reranked_sections if s.section_id] if reranked_sections else None
        final_hits = reranked_sections
        limited: list[RetrievalHit] = []
        if chunks_enabled:
            chunk_where = where
            clauses = []
            if doc_ids:
                clauses.append({"doc_id": {"$in": doc_ids}})
            if section_ids:
                clauses.append({"section_id": {"$in": section_ids}})
            if clauses:
                if "$and" in chunk_where:
                    chunk_where = {"$and": chunk_where.get("$and", []) + clauses}
                else:
                    chunk_where = {"$and": clauses + [where]}

            n_results = min(self.chunk_top_k, max_results * 3) if self.chunk_top_k else max_results * 3
            self._logger.info(
                "retrieval_stage_start",
                stage="chunks",
                collection=getattr(self.collection, "name", self.collection.name if hasattr(self.collection, "name") else "ingestion_chunks"),
                where=chunk_where,
                requested=n_results,
            )
            hits = self._search_collection(
                self.collection,
                query_embedding,
                chunk_where,
                n_results,
                is_chunk=True,
                tags_filter=tags_filter,
            )

            # enforce per-doc limit and max_results
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
                limited = self._fallback_metadata_search(query, chunk_where, max_results, tags_filter=tags_filter)
            steps.chunks = limited
            if not final_hits:
                final_hits = limited
        else:
            self._logger.info("retrieval_stage_skipped", stage="chunks", reason="disabled")
            steps.chunks = []
        self._logger.info(
            "retrieval_chroma_results",
            tenant_id=query.tenant_id,
            hits=len(final_hits),
            requested=max_results,
            total_raw=len(limited) if chunks_enabled else 0,
        )
        if rerank_snapshot:
            kept_ids = {(h.doc_id, h.section_id) for h in reranked_sections}
            discarded = [
                {"doc_id": h.doc_id, "section_id": h.section_id, "rerank_score": h.rerank_score or h.score}
                for h in rerank_snapshot
                if (h.doc_id, h.section_id) not in kept_ids
            ]
            if discarded:
                self._logger.info("retrieval_rerank_discarded", count=len(discarded), sections=discarded)
        if reranked_sections:
            self._logger.info(
                "retrieval_final_sections",
                total=len(reranked_sections),
                sections=[
                    {"doc_id": h.doc_id, "section_id": h.section_id, "score": h.score, "rerank_score": h.rerank_score}
                    for h in reranked_sections
                ],
            )
        if not final_hits:
            self._log_metadata_keys(self.collection, chunk_where, stage="chunks", tags_filter=tags_filter)
        return final_hits[:max_results], steps

    def _search_collection(self, collection, query_embedding, where: dict, n_results: int, is_doc: bool = False, is_section: bool = False, is_chunk: bool = False, tags_filter: Set[str] | None = None) -> List[RetrievalHit]:
        if not collection:
            return []
        try:
            res = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["metadatas", "distances", "documents"],
            )
        except Exception as exc:  # pragma: no cover - runtime path
            self._logger.warning("retrieval_query_failed", error=str(exc))
            return []
        ids = res.get("ids", [[]])[0] if res else []
        metas = res.get("metadatas", [[]])[0] if res else []
        distances = res.get("distances", [[]])[0] if res else []
        hits = []
        for cid, meta, dist in zip(ids, metas, distances):
            if not meta:
                continue
            if tags_filter and not self._metadata_matches_tags(meta.get("tags"), tags_filter):
                continue
            score = 1 - dist if dist is not None else 0.0
            summary = meta.get("summary") or meta.get("title") or meta.get("name") or ""
            doc_id = meta.get("doc_id") or (cid if is_doc else meta.get("doc_id") or "")
            title = meta.get("title") or meta.get("name") or meta.get("summary") or summary
            raw_chunk_ids = meta.get("chunk_ids") if is_section else None
            if isinstance(raw_chunk_ids, str):
                chunk_ids = [c.strip() for c in raw_chunk_ids.split(",") if c.strip()]
            elif isinstance(raw_chunk_ids, list):
                chunk_ids = raw_chunk_ids
            else:
                chunk_ids = None
            anchor_chunk_id = chunk_ids[0] if chunk_ids else None
            hits.append(
                RetrievalHit(
                    doc_id=doc_id,
                    section_id=meta.get("section_id") if not is_doc else None,
                    chunk_id=meta.get("chunk_id") if is_chunk else None,
                    text=summary,
                    score=score,
                    page_start=meta.get("page_start"),
                    page_end=meta.get("page_end"),
                    chunk_ids=chunk_ids,
                    anchor_chunk_id=anchor_chunk_id if is_section else None,
                    title=title,
                    summary=summary or meta.get("summary"),
                    page=meta.get("page"),
                    chunk_index=meta.get("chunk_index"),
                )
            )
        return hits

    def _fallback_metadata_search(self, query: RetrievalQuery, where: dict, max_results: int, tags_filter: Set[str] | None = None) -> List[RetrievalHit]:
        try:
            res = self.collection.get(where=where, include=["metadatas"], limit=500)
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
            if tags_filter and not self._metadata_matches_tags(meta.get("tags"), tags_filter):
                continue
            raw_text = (meta.get("text") or "").lower()
            if q in raw_text:
                summary = meta.get("summary") or meta.get("title") or meta.get("name") or ""
                hits.append(
                    RetrievalHit(
                        doc_id=meta.get("doc_id", "") or cid,
                        section_id=meta.get("section_id"),
                        chunk_id=meta.get("chunk_id") or cid,
                        text=summary,
                        score=0.1,
                        page_start=meta.get("page_start"),
                        page_end=meta.get("page_end"),
                        chunk_ids=meta.get("chunk_ids"),
                        title=meta.get("title") or meta.get("name") or meta.get("summary"),
                        summary=summary,
                        page=meta.get("page"),
                        chunk_index=meta.get("chunk_index"),
                    )
                )
        hits = hits[:max_results]
        if hits:
            self._logger.info("retrieval_metadata_fallback_used", hits=len(hits))
        return hits

    def _pad_docs_with_metadata(self, where: dict, existing_doc_ids: List[str], need: int, tags_filter: Set[str] | None = None) -> List[RetrievalHit]:
        try:
            res = self.doc_collection.get(where=where, include=["metadatas"], limit=need * 2) if self.doc_collection else None
        except Exception as exc:  # pragma: no cover
            self._logger.warning("retrieval_doc_pad_failed", error=str(exc), where=where, need=need)
            return []
        if not res:
            return []
        ids = res.get("ids") or []
        metas = res.get("metadatas") or []
        padded: List[RetrievalHit] = []
        for cid, meta in zip(ids, metas):
            if cid in existing_doc_ids:
                continue
            if tags_filter and not self._metadata_matches_tags(meta.get("tags"), tags_filter):
                continue
            doc_id = meta.get("doc_id") or cid
            title = meta.get("title") or meta.get("name") or meta.get("summary") or ""
            padded.append(
                RetrievalHit(
                    doc_id=doc_id,
                    section_id=None,
                    chunk_id=cid,
                    text=title,
                    score=0.0,
                    title=title,
                    summary=title,
                )
            )
            if len(padded) >= need:
                break
        if padded:
            self._logger.info("retrieval_docs_padded", padded=len(padded))
        return padded

    @staticmethod
    def _metadata_matches_tags(meta_value, tags_filter: Set[str]) -> bool:
        if not tags_filter:
            return True
        if not meta_value:
            return False
        if isinstance(meta_value, str):
            stored = {t.strip().lower() for t in meta_value.split(",") if t.strip()}
        elif isinstance(meta_value, (list, tuple, set)):
            stored = {str(t).strip().lower() for t in meta_value}
        else:
            stored = {str(meta_value).lower()}
        return bool(stored.intersection(tags_filter))

    def _log_metadata_keys(self, collection, where: dict, stage: str, tags_filter: Set[str] | None = None) -> None:
        if not collection:
            return
        try:
            sample = collection.get(where=where, include=["metadatas"], limit=3)
        except Exception as exc:  # pragma: no cover - diagnostics only
            self._logger.warning("retrieval_metadata_probe_failed", stage=stage, error=str(exc), where=where)
            return
        metas = sample.get("metadatas") or []
        keys = sorted({k for meta in metas if isinstance(meta, dict) for k in meta.keys()})
        self._logger.info(
            "retrieval_metadata_keys",
            stage=stage,
            where=where,
            tags_filter=list(tags_filter) if tags_filter else None,
            keys=keys,
        )
