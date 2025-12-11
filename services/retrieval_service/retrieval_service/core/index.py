from __future__ import annotations

from typing import List

from retrieval_service.schemas import RetrievalHit, RetrievalQuery


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
        results = [hit for hit in self.documents if q in hit.text.lower()]
        return results[: query.max_results or len(results)]
