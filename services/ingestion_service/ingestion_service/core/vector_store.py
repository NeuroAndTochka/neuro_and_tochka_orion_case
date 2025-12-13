from __future__ import annotations

from typing import Iterable, List, Sequence

try:  # pragma: no cover - optional dependency in tests
    import chromadb  # type: ignore
except Exception:
    chromadb = None  # type: ignore


class VectorStore:
    """Wrapper над ChromaDB с in-memory fallback."""

    def __init__(self, path: str, host: str | None = None, enabled: bool = True):
        self.enabled = enabled and chromadb is not None
        if self.enabled:
            if host:
                client = chromadb.HttpClient(host=host)  # type: ignore[arg-type]
            else:
                client = chromadb.PersistentClient(path=path)
            self.doc_collection = client.get_or_create_collection("ingestion_docs")
            self.section_collection = client.get_or_create_collection("ingestion_sections")
            self.chunk_collection = client.get_or_create_collection("ingestion_chunks")
        else:
            self.doc_collection = None
            self.section_collection = None
            self.chunk_collection = None
            self._docs: list[dict] = []
            self._sections: list[dict] = []
            self._chunks: list[dict] = []

    def upsert_document(self, doc_id: str, tenant_id: str, embedding: Sequence[float], metadata: dict) -> None:
        if self.enabled and self.doc_collection:
            self.doc_collection.upsert(
                ids=[doc_id],
                embeddings=[list(embedding)],
                metadatas=[{"tenant_id": tenant_id, **metadata}],
            )
        else:
            self._docs.append({"id": doc_id, "tenant_id": tenant_id, "embedding": list(embedding), "metadata": metadata})

    @staticmethod
    def _sanitize_meta(meta: dict) -> dict:
        """Chroma требует простые типы; списки/сложные структуры переводим в строки."""
        def convert(value):
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            if isinstance(value, (list, tuple, set)):
                return ", ".join(map(str, value))
            if isinstance(value, dict):
                return ", ".join(f"{k}:{v}" for k, v in value.items())
            return str(value)

        return {k: convert(v) for k, v in meta.items()}

    def upsert_sections(
        self,
        doc_id: str,
        tenant_id: str,
        section_embeddings: List[Sequence[float]],
        sections_payload: Iterable[dict],
    ) -> None:
        ids = []
        metas = []
        embs = []
        for payload, emb in zip(sections_payload, section_embeddings):
            ids.append(f"{doc_id}:{payload['section_id']}")
            raw_meta = {"tenant_id": tenant_id, "doc_id": doc_id, **{k: v for k, v in payload.items() if k != "embedding"}}
            metas.append(self._sanitize_meta(raw_meta))
            embs.append(list(emb))
        if self.enabled and self.section_collection:
            self.section_collection.upsert(ids=ids, embeddings=embs, metadatas=metas)
        else:
            for i, m, e in zip(ids, metas, embs):
                self._sections.append({"id": i, "metadata": m, "embedding": e})

    def upsert_chunks(
        self,
        doc_id: str,
        tenant_id: str,
        chunk_embeddings: List[Sequence[float]],
        chunk_pairs: List[tuple[str, str]],
    ) -> None:
        ids = []
        metas = []
        embs = []
        for (chunk_id, chunk_text), emb in zip(chunk_pairs, chunk_embeddings):
            ids.append(f"{doc_id}:{chunk_id}")
            raw_meta = {"tenant_id": tenant_id, "doc_id": doc_id, "chunk_id": chunk_id, "text": chunk_text}
            metas.append(self._sanitize_meta(raw_meta))
            embs.append(list(emb))
        if self.enabled and self.chunk_collection:
            self.chunk_collection.upsert(ids=ids, embeddings=embs, metadatas=metas)
        else:
            for i, m, e in zip(ids, metas, embs):
                self._chunks.append({"id": i, "metadata": m, "embedding": e})

    def get_chunks(self, doc_id: str, tenant_id: str) -> List[dict]:
        if self.enabled and self.chunk_collection:
            where = {"$and": [{"doc_id": doc_id}, {"tenant_id": tenant_id}]}
            res = self.chunk_collection.get(
                where=where,
                include=["metadatas"],
            )
            metadatas = res.get("metadatas") or []
            ids = res.get("ids") or []
            result = []
            for cid, meta in zip(ids, metadatas):
                entry = {"id": cid}
                if meta:
                    entry.update(meta)
                result.append(entry)
            return result
        return [
            c["metadata"]
            for c in getattr(self, "_chunks", [])
            if c.get("metadata", {}).get("doc_id") == doc_id and c.get("metadata", {}).get("tenant_id") == tenant_id
        ]
