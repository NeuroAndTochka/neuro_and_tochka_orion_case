from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from document_service.schemas import DocumentDetail, DocumentItem, DocumentSection


class InMemoryRepository:
    def __init__(self) -> None:
        now = datetime.utcnow()
        sections = [
            DocumentSection(section_id="sec_intro", title="Введение", page_start=1, page_end=3, chunk_ids=["chunk_1", "chunk_2"]),
            DocumentSection(section_id="sec_setup", title="Настройка", page_start=4, page_end=10, chunk_ids=["chunk_3"]),
        ]
        detail = DocumentDetail(
            doc_id="doc_1",
            title="Orion LDAP Guide",
            pages=142,
            tenant_id="tenant_1",
            tags=["ldap", "admin"],
            sections=sections,
        )
        self.documents: Dict[str, DocumentDetail] = {detail.doc_id: detail}
        self.items: Dict[str, DocumentItem] = {
            detail.doc_id: DocumentItem(
                doc_id=detail.doc_id,
                name=detail.title,
                status="indexed",
                product="Orion X",
                version="1.2",
                tags=detail.tags,
                updated_at=now,
            )
        }

    def list_documents(self, tenant_id: str, filters: Dict[str, str]) -> List[DocumentItem]:
        results = []
        for item in self.items.values():
            detail = self.documents[item.doc_id]
            if detail.tenant_id != tenant_id:
                continue
            if filters.get("status") and item.status != filters["status"]:
                continue
            if filters.get("product") and item.product != filters["product"]:
                continue
            if filters.get("tag") and filters["tag"] not in item.tags:
                continue
            if filters.get("search") and filters["search"].lower() not in item.name.lower():
                continue
            results.append(item)
        return results

    def get_document(self, doc_id: str) -> Optional[DocumentDetail]:
        return self.documents.get(doc_id)

    def update_status(self, doc_id: str, status: str, error: Optional[str]) -> DocumentItem:
        item = self.items.get(doc_id)
        if not item:
            raise KeyError(doc_id)
        item.status = status
        item.updated_at = datetime.utcnow()
        return item

    def get_section(self, doc_id: str, section_id: str) -> Optional[DocumentSection]:
        detail = self.documents.get(doc_id)
        if not detail:
            return None
        for section in detail.sections:
            if section.section_id == section_id:
                return section
        return None
