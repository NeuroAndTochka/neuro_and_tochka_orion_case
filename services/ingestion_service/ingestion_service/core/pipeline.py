from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Sequence
from urllib.parse import urlparse

import httpx
import structlog

from ingestion_service.core.embedding import EmbeddingClient
from ingestion_service.core.jobs import JobStore
from ingestion_service.core.parser import DocumentParser
from ingestion_service.core.summarizer import Summarizer
from ingestion_service.core.storage import StorageClient
from ingestion_service.schemas import IngestionTicket

logger = structlog.get_logger(__name__)


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
    summarizer: Summarizer,
    jobs: JobStore,
    doc_service_base_url: str | None,
    max_pages: int,
    max_file_mb: int,
    chunk_size: int,
    vector_store,
) -> None:
    tmp_file: Path | None = None
    try:
        content_bytes = storage.download_bytes(ticket.storage_uri or "")
        tmp_path = storage.resolve_local_path(ticket.storage_uri or "") if ticket.storage_uri else None
        # Для S3/remote URI пишем во временный файл, чтобы парсер (PyPDF2/docx) корректно работал.
        if not tmp_path or not tmp_path.exists():
            parsed = urlparse(ticket.storage_uri or "")
            suffix = Path(parsed.path).suffix or ".bin"
            fh = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            fh.write(content_bytes)
            fh.flush()
            fh.close()
            tmp_path = Path(fh.name)
            tmp_file = tmp_path

        parser = DocumentParser(max_pages=max_pages, max_file_mb=max_file_mb)
        text = DocumentParser._clean_text(content_bytes.decode("utf-8", errors="ignore"))
        if tmp_path and tmp_path.exists():
            pages, meta = parser.parse(tmp_path)
            text = "\n".join(pages)
        else:
            pages = [text]
            meta = {"pages": len(pages), "title": "unknown"}
        logger.debug(
            "ingestion_parsed",
            doc_id=ticket.doc_id,
            tenant_id=ticket.tenant_id,
            pages=len(pages),
            chunk_size=chunk_size,
        )

        sections, chunk_pairs = _build_sections_from_pages(pages, chunk_size)
        chunk_texts = [c[1] for c in chunk_pairs]

        # Embeddings: документ, секции, чанки
        doc_embedding = embedding.embed([text])[0]
        section_embeddings = embedding.embed([s["text"] for s in sections])
        chunk_embeddings = embedding.embed(chunk_texts) if chunk_texts else []
        logger.debug(
            "ingestion_embeddings_ready",
            doc_id=ticket.doc_id,
            tenant_id=ticket.tenant_id,
            sections=len(sections),
            chunks=len(chunk_pairs),
        )
        log_entry = {
            "type": "embedding",
            "stage": "document",
            "model": embedding.settings.embedding_model if hasattr(embedding, "settings") else None,
            "items": 1,
            "dimensions": len(doc_embedding) if doc_embedding else 0,
            "status": "ok",
        }
        jobs.append_log(ticket.job_id, log_entry)
        logger.info("model_call", job_id=ticket.job_id, doc_id=ticket.doc_id, tenant_id=ticket.tenant_id, **log_entry)

        jobs.append_log(
            ticket.job_id,
            {
                "type": "embedding_payload",
                "stage": "document",
                "input": text,
            },
        )

        log_entry = {
            "type": "embedding",
            "stage": "sections",
            "model": embedding.settings.embedding_model if hasattr(embedding, "settings") else None,
            "items": len(sections),
            "dimensions": len(section_embeddings[0]) if section_embeddings else 0,
            "status": "ok",
        }
        jobs.append_log(ticket.job_id, log_entry)
        logger.info("model_call", job_id=ticket.job_id, doc_id=ticket.doc_id, tenant_id=ticket.tenant_id, **log_entry)
        jobs.append_log(
            ticket.job_id,
            {
                "type": "embedding_payload",
                "stage": "sections",
                "input": [s["text"] for s in sections],
            },
        )
        if chunk_embeddings:
            log_entry = {
                "type": "embedding",
                "stage": "chunks",
                "model": embedding.settings.embedding_model if hasattr(embedding, "settings") else None,
                "items": len(chunk_embeddings),
                "dimensions": len(chunk_embeddings[0]) if chunk_embeddings else 0,
                "status": "ok",
            }
            jobs.append_log(ticket.job_id, log_entry)
            logger.info("model_call", job_id=ticket.job_id, doc_id=ticket.doc_id, tenant_id=ticket.tenant_id, **log_entry)
            jobs.append_log(
                ticket.job_id,
                {
                    "type": "embedding_payload",
                    "stage": "chunks",
                    "input": chunk_texts,
                },
            )

        # LLM summary для секций
        try:
            section_summaries = summarizer.summarize([s["text"] for s in sections])
            log_entry = {
                "type": "summary",
                "stage": "sections",
                "model": getattr(summarizer, "model", None),
                "items": len(section_summaries),
                "status": "ok",
                "preview": [s[:200] for s in section_summaries[:3]],
            }
            jobs.append_log(ticket.job_id, log_entry)
            logger.info("model_call", job_id=ticket.job_id, doc_id=ticket.doc_id, tenant_id=ticket.tenant_id, **log_entry)
            jobs.append_log(
                ticket.job_id,
                {
                    "type": "summary_payload",
                    "stage": "sections",
                    "system_prompt": getattr(summarizer, "system_prompt", None),
                    "requests": [{"section_id": sec["section_id"], "prompt": sec["text"][:4000]} for sec in sections],
                    "responses": [
                        {"section_id": sec["section_id"], "summary": summary}
                        for sec, summary in zip(sections, section_summaries)
                    ],
                },
            )
        except Exception:
            log_entry = {
                "type": "summary",
                "stage": "sections",
                "model": getattr(summarizer, "model", None),
                "items": len(sections),
                "status": "fallback",
            }
            jobs.append_log(ticket.job_id, log_entry)
            logger.info("model_call", job_id=ticket.job_id, doc_id=ticket.doc_id, tenant_id=ticket.tenant_id, **log_entry)
            section_summaries = [DocumentParser._clean_text(s["text"])[:200] for s in sections]

        sections_payload = []
        for sec, emb, summary in zip(sections, section_embeddings, section_summaries):
            payload = {
                "section_id": sec["section_id"],
                "title": sec["title"],
                "page_start": sec["page_start"],
                "page_end": sec["page_end"],
                "chunk_ids": sec["chunk_ids"],
                "summary": summary,
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
                logger.debug(
                    "ingestion_document_service_updated",
                    doc_id=ticket.doc_id,
                    tenant_id=ticket.tenant_id,
                    sections=len(sections_payload),
                )
            except Exception:
                logger.exception("ingestion_document_service_update_failed", doc_id=ticket.doc_id, tenant_id=ticket.tenant_id)

        # vector store запись
        if vector_store:
            vector_store.upsert_document(ticket.doc_id, ticket.tenant_id, doc_embedding, {"title": meta.get("title")})
            vector_store.upsert_sections(ticket.doc_id, ticket.tenant_id, section_embeddings, sections_payload)
            if chunk_embeddings:
                vector_store.upsert_chunks(ticket.doc_id, ticket.tenant_id, chunk_embeddings, chunk_pairs)
            logger.debug(
                "ingestion_vectorstore_upserted",
                doc_id=ticket.doc_id,
                tenant_id=ticket.tenant_id,
                sections=len(sections_payload),
                chunks=len(chunk_pairs),
            )

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
    finally:
        if tmp_file and tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass
