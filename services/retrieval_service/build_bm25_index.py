#!/usr/bin/env python3
"""
One-off builder for BM25 index from existing Chroma chunks.
Usage: python build_bm25_index.py
Respects RETR_* env from .env (chroma host/path, collection name, bm25 index path).
"""

from pathlib import Path
import os

from chromadb import HttpClient, PersistentClient
from urllib.parse import urlparse

from retrieval_service.config import get_settings
from retrieval_service.core.bm25 import BM25Index, ensure_index_dir


def get_chroma_collection(settings):
    if settings.chroma_host:
        parsed = urlparse(settings.chroma_host)
        client = HttpClient(host=parsed.hostname or settings.chroma_host, port=parsed.port or 8000, ssl=parsed.scheme == "https")
    else:
        client = PersistentClient(path=settings.chroma_path)
    return client.get_collection(name=settings.chroma_collection)


def main() -> None:
    settings = get_settings()
    idx_dir = ensure_index_dir(settings.bm25_index_path)
    if not Path(idx_dir).exists() or not any(Path(idx_dir).iterdir()):
        BM25Index.create(idx_dir)

    from whoosh import index  # lazy import

    ix = index.open_dir(idx_dir)
    writer = ix.writer(limitmb=512, procs=0, multisegment=True)

    coll = get_chroma_collection(settings)
    count = coll.count()
    batch = 500
    print(f"Total chunks: {count}")
    for offset in range(0, count, batch):
        resp = coll.get(
            include=["documents", "metadatas"],
            limit=batch,
            offset=offset,
        )
        docs = resp.get("documents") or []
        metas = resp.get("metadatas") or []
        ids = resp.get("ids") or []
        for doc_id_val, meta, doc in zip(ids, metas, docs):
            if not doc:
                continue
            writer.update_document(
                doc_id=str(meta.get("doc_id") or ""),
                section_id=str(meta.get("section_id") or ""),
                chunk_id=str(doc_id_val),
                text=str(doc),
            )
    writer.commit(optimize=True)
    print(f"Index built at {idx_dir}")


if __name__ == "__main__":
    main()
