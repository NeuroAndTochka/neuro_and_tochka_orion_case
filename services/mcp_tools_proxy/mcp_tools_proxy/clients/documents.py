from __future__ import annotations

from typing import Dict, List, Optional

from mcp_tools_proxy.schemas import DocumentMetadata


class DocumentRepository:
    def __init__(self, mock_mode: bool = True) -> None:
        self.mock_mode = mock_mode
        self._metadata: Dict[str, DocumentMetadata] = {}
        self._content: Dict[str, str] = {}
        if mock_mode:
            self._seed()

    def _seed(self) -> None:
        metadata = DocumentMetadata(
            doc_id="doc_1",
            title="Orion LDAP Guide",
            pages=12,
            tags=["orion", "ldap"],
            sections=[
                {
                    "section_id": "sec_intro",
                    "title": "Introduction",
                    "page_start": 1,
                    "page_end": 2,
                },
                {
                    "section_id": "sec_setup",
                    "title": "Setup",
                    "page_start": 3,
                    "page_end": 5,
                },
                {
                    "section_id": "sec_troubleshooting",
                    "title": "Troubleshooting",
                    "page_start": 6,
                    "page_end": 8,
                },
            ],
            tenant_id="tenant_1",
        )
        self._metadata[metadata.doc_id] = metadata
        self._content[metadata.doc_id] = (
            "Intro..." * 100
            + "Setup instructions..." * 100
            + "Troubleshooting section..." * 100
            + "Final notes" * 50
        )

    def get_metadata(self, doc_id: str) -> Optional[DocumentMetadata]:
        return self._metadata.get(doc_id)

    def read_section_text(self, doc_id: str, section_id: str) -> Optional[str]:
        meta = self._metadata.get(doc_id)
        if not meta:
            return None
        for section in meta.sections:
            if section.section_id == section_id:
                return self._slice_content(doc_id, section.page_start, section.page_end)
        return None

    def read_pages(self, doc_id: str, page_start: int, page_end: int) -> Optional[str]:
        meta = self._metadata.get(doc_id)
        if not meta or page_start > meta.pages:
            return None
        return self._slice_content(doc_id, page_start, min(page_end, meta.pages))

    def local_search(self, doc_id: str, query: str, max_results: int) -> List[Dict[str, str]]:
        content = self._content.get(doc_id, "")
        snippets: List[Dict[str, str]] = []
        if not query:
            return snippets
        lowered = content.lower()
        q = query.lower()
        start = 0
        while len(snippets) < max_results:
            idx = lowered.find(q, start)
            if idx == -1:
                break
            window_start = max(0, idx - 80)
            window_end = min(len(content), idx + len(q) + 80)
            snippet = content[window_start:window_end]
            snippets.append({"snippet": snippet.strip()})
            start = idx + len(q)
        return snippets

    def _slice_content(self, doc_id: str, page_start: int, page_end: int) -> Optional[str]:
        content = self._content.get(doc_id)
        if not content:
            return None
        # simple heuristic: 500 chars per page
        page_len = 500
        start_idx = (page_start - 1) * page_len
        end_idx = page_end * page_len
        return content[start_idx:end_idx]
