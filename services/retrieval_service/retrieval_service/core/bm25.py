from __future__ import annotations

import os
from typing import List, Optional

from whoosh import index
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import MultifieldParser
from whoosh.scoring import BM25F

from retrieval_service.schemas import RetrievalHit


class BM25Index:
    def __init__(self, index_path: str) -> None:
        self.index_path = index_path
        self._ix = index.open_dir(index_path)
        self._searcher = self._ix.searcher(weighting=BM25F(B=0.75, K1=1.5))
        self._parser = MultifieldParser(["text"], schema=self._ix.schema)

    @staticmethod
    def create(index_path: str) -> None:
        os.makedirs(index_path, exist_ok=True)
        schema = Schema(
            doc_id=ID(stored=True),
            section_id=ID(stored=True),
            chunk_id=ID(stored=True, unique=True),
            text=TEXT(stored=False),
        )
        index.create_in(index_path, schema)

    def search(self, query: str, top_k: int) -> List[RetrievalHit]:
        if not query.strip():
            return []
        parsed = self._parser.parse(query)
        results = self._searcher.search(parsed, limit=top_k)
        hits: List[RetrievalHit] = []
        for hit in results:
            hits.append(
                RetrievalHit(
                    doc_id=hit["doc_id"],
                    section_id=hit["section_id"],
                    chunk_id=hit["chunk_id"],
                    score=float(hit.score),
                    bm25_score=float(hit.score),
                )
            )
        return hits


def ensure_index_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
