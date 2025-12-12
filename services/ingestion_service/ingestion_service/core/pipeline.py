from __future__ import annotations

from typing import List, Sequence

import httpx

from ingestion_service.core.embedding import EmbeddingClient
from ingestion_service.core.jobs import JobStore
from ingestion_service.core.parser import DocumentParser
from ingestion_service.core.storage import StorageClient
from ingestion_service.schemas import IngestionTicket


def _split_chunks(text: str, max_len: int = 2048) -> List[str]:
    words = text.split()
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for w in words:
        current.append(w)
        current_len += len(w) + 1
        if current_len >= max_len:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _build_sections_from_pages(pages: Sequence[str], chunk_size: int) -> tuple[List[dict], List[tuple[str, str]]]:
    """Возвращает секции и список (chunk_id, chunk_text)."""
    sections: List[dict] = []
    chunks: List[tuple[str, str]] = []
    for idx, page_text in enumerate(pages, start=1):
        section_id = f"sec_{idx}"
        page_chunks = _split_chunks(page_text, max_len=chunk_size)
        chunk_ids = []
        for c_idx, chunk_text in enumerate(page_chunks, start=1):
            cid = f"chunk_{idx}_{c_idx}"
            chunk_ids.append(cid)
            chunks.append((cid, chunk_text))
        sections.append(
            {
                "section_id": section_id,
                "title": f"Page {idx}",
                "page_start": idx,
                "page_end": idx,
                "chunk_ids": chunk_ids,
                "summary": page_text[:200],
                "storage_path": None,
                "text": page_text,
            }
        )
    return sections, chunks


def process_file(
    *,
    ticket: IngestionTicket,
    storage: StorageClient,
    embedding: EmbeddingClient,
    jobs: JobStore,
    doc_service_base_url: str | None,
    max_pages: int,
    max_file_mb: int,
    chunk_size: int,
    vector_store,
) -> None:
    try:
        content_bytes = storage.download_bytes(ticket.storage_uri or "")
        tmp_path = storage.resolve_local_path(ticket.storage_uri or "") if ticket.storage_uri else None
        parser = DocumentParser(max_pages=max_pages, max_file_mb=max_file_mb)
        text = content_bytes.decode("utf-8", errors="ignore")
        if tmp_path and tmp_path.exists():
            pages, meta = parser.parse(tmp_path)
            text = "\n".join(pages)
        else:
            pages = [text]
            meta = {"pages": len(pages), "title": "unknown"}

        sections, chunk_pairs = _build_sections_from_pages(pages, chunk_size)
        chunk_texts = [c[1] for c in chunk_pairs]

        # Embeddings: документ, секции, чанки
        doc_embedding = embedding.embed([text])[0]
        section_embeddings = embedding.embed([s["text"] for s in sections])
        chunk_embeddings = embedding.embed(chunk_texts) if chunk_texts else []

        sections_payload = []
        for sec, emb in zip(sections, section_embeddings):
            payload = {
                "section_id": sec["section_id"],
                "title": sec["title"],
                "page_start": sec["page_start"],
                "page_end": sec["page_end"],
                "chunk_ids": sec["chunk_ids"],
                "summary": sec["summary"],
                "storage_path": sec["storage_path"],
            }
            payload["embedding"] = emb  # можно игнорировать на стороне Document Service
            sections_payload.append(payload)

        if doc_service_base_url:
            try:
                with httpx.Client(timeout=10.0) as client:
                    client.post(
                        f"{doc_service_base_url}/internal/documents/{ticket.doc_id}/sections",
                        json={"sections": sections_payload},
                        headers={"X-Tenant-ID": ticket.tenant_id},
                    )
                    client.post(
                        f"{doc_service_base_url}/internal/documents/status",
                        json={
                            "doc_id": ticket.doc_id,
                            "status": "indexed",
                            "storage_uri": ticket.storage_uri,
                            "pages": meta.get("pages", len(pages)),
                        },
                        headers={"X-Tenant-ID": ticket.tenant_id},
                    )
            except Exception:
                pass

        # vector store запись
        if vector_store:
            vector_store.upsert_document(ticket.doc_id, ticket.tenant_id, doc_embedding, {"title": meta.get("title")})
            vector_store.upsert_sections(ticket.doc_id, ticket.tenant_id, section_embeddings, sections_payload)
            if chunk_embeddings:
                vector_store.upsert_chunks(ticket.doc_id, ticket.tenant_id, chunk_embeddings, chunk_pairs)

        jobs.update(ticket.job_id, status="indexed", storage_uri=ticket.storage_uri)
        jobs.publish_event(
            {
                "event": "document_ingested",
                "doc_id": ticket.doc_id,
                "tenant_id": ticket.tenant_id,
                "sections": len(sections),
                "chunks": len(chunk_texts),
            }
        )
    except Exception as exc:  # pragma: no cover
        jobs.update(ticket.job_id, status="failed", error=str(exc))
        jobs.publish_event({"event": "ingestion_failed", "doc_id": ticket.doc_id, "tenant_id": ticket.tenant_id, "error": str(exc)})
