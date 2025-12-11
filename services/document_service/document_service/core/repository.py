from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from document_service import models
from document_service.schemas import (
    DocumentCreateRequest,
    DocumentDetail,
    DocumentItem,
    DocumentSection,
    SectionUpsertItem,
    StatusUpdateRequest,
)


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_or_update_document(self, payload: DocumentCreateRequest) -> DocumentDetail:
        document = await self.session.get(
            models.Document,
            payload.doc_id,
            options=[selectinload(models.Document.tags), selectinload(models.Document.sections)],
        )
        if document is None:
            document = models.Document(doc_id=payload.doc_id, tenant_id=payload.tenant_id)
            self.session.add(document)
        elif document.tenant_id != payload.tenant_id:
            raise PermissionError("document belongs to a different tenant")

        document.name = payload.name
        document.product = payload.product
        document.version = payload.version
        document.status = payload.status
        document.storage_uri = payload.storage_uri
        document.pages = payload.pages
        await self._replace_tags(document, payload.tags)
        await self.session.commit()
        return await self.get_document(document.doc_id, document.tenant_id)

    async def list_documents(
        self,
        tenant_id: str,
        filters: dict[str, str],
        limit: int,
        offset: int,
    ) -> Tuple[int, List[DocumentItem]]:
        base_stmt = select(models.Document).where(
            models.Document.tenant_id == tenant_id, models.Document.deleted_at.is_(None)
        )
        count_stmt = (
            select(func.count(func.distinct(models.Document.doc_id)))
            .select_from(models.Document)
            .where(models.Document.tenant_id == tenant_id, models.Document.deleted_at.is_(None))
        )

        if status := filters.get("status"):
            base_stmt = base_stmt.where(models.Document.status == status)
            count_stmt = count_stmt.where(models.Document.status == status)
        if product := filters.get("product"):
            base_stmt = base_stmt.where(models.Document.product == product)
            count_stmt = count_stmt.where(models.Document.product == product)
        if search := filters.get("search"):
            pattern = f"%{search.lower()}%"
            base_stmt = base_stmt.where(func.lower(models.Document.name).like(pattern))
            count_stmt = count_stmt.where(func.lower(models.Document.name).like(pattern))
        if tag := filters.get("tag"):
            base_stmt = base_stmt.join(models.Document.tags).where(models.DocumentTag.tag == tag)
            count_stmt = count_stmt.join(models.Document.tags).where(models.DocumentTag.tag == tag)

        base_stmt = base_stmt.order_by(models.Document.updated_at.desc()).limit(limit).offset(offset)
        base_stmt = base_stmt.options(selectinload(models.Document.tags))

        total = await self.session.scalar(count_stmt)
        docs = (await self.session.scalars(base_stmt)).unique().all()
        items = [self._to_item(doc) for doc in docs]
        return int(total or 0), items

    async def get_document(self, doc_id: str, tenant_id: str) -> Optional[DocumentDetail]:
        stmt = (
            select(models.Document)
            .where(
                models.Document.doc_id == doc_id,
                models.Document.tenant_id == tenant_id,
                models.Document.deleted_at.is_(None),
            )
            .options(selectinload(models.Document.tags), selectinload(models.Document.sections))
        )
        document = (await self.session.scalars(stmt)).first()
        if not document:
            return None
        return self._to_detail(document)

    async def get_section(self, doc_id: str, section_id: str, tenant_id: str) -> Optional[DocumentSection]:
        stmt = (
            select(models.DocumentSection)
            .join(models.Document)
            .where(
                models.DocumentSection.doc_id == doc_id,
                models.Document.tenant_id == tenant_id,
                models.DocumentSection.section_id == section_id,
            )
        )
        section = (await self.session.scalars(stmt)).first()
        if not section:
            return None
        return self._to_section(section)

    async def update_status(self, payload: StatusUpdateRequest) -> Optional[str]:
        document = await self.session.get(
            models.Document,
            payload.doc_id,
            options=[selectinload(models.Document.tags)],
        )
        if not document:
            return None
        document.status = payload.status
        document.last_error = payload.error
        if payload.storage_uri is not None:
            document.storage_uri = payload.storage_uri
        if payload.pages is not None:
            document.pages = payload.pages
        tenant_id = document.tenant_id
        await self.session.commit()
        return tenant_id

    async def upsert_sections(
        self,
        doc_id: str,
        tenant_id: str,
        sections: Sequence[SectionUpsertItem],
    ) -> Optional[DocumentDetail]:
        document = await self.session.get(
            models.Document,
            doc_id,
            options=[selectinload(models.Document.tags), selectinload(models.Document.sections)],
        )
        if not document or document.tenant_id != tenant_id:
            return None
        existing_sections = {section.section_id: section for section in document.sections}
        for data in sections:
            section = existing_sections.get(data.section_id)
            if section is None:
                section = models.DocumentSection(section_id=data.section_id, doc_id=doc_id)
                document.sections.append(section)
            section.title = data.title
            section.page_start = data.page_start
            section.page_end = data.page_end
            section.chunk_ids = list(data.chunk_ids)
            section.summary = data.summary
            section.storage_path = data.storage_path
        await self.session.commit()
        return await self.get_document(doc_id, tenant_id)

    async def _replace_tags(self, document: models.Document, tags: Iterable[str]) -> None:
        new_tags = {tag for tag in tags}
        document.tags = [models.DocumentTag(tag=tag) for tag in new_tags]

    def _to_item(self, document: models.Document) -> DocumentItem:
        return DocumentItem(
            doc_id=document.doc_id,
            name=document.name,
            status=document.status,
            product=document.product,
            version=document.version,
            tags=[tag.tag for tag in document.tags],
            updated_at=document.updated_at,
        )

    def _to_section(self, section: models.DocumentSection) -> DocumentSection:
        return DocumentSection(
            section_id=section.section_id,
            title=section.title,
            page_start=section.page_start,
            page_end=section.page_end,
            chunk_ids=section.chunk_ids or [],
            summary=section.summary,
            storage_path=section.storage_path,
        )

    def _to_detail(self, document: models.Document) -> DocumentDetail:
        return DocumentDetail(
            doc_id=document.doc_id,
            name=document.name,
            tenant_id=document.tenant_id,
            status=document.status,
            product=document.product,
            version=document.version,
            storage_uri=document.storage_uri,
            pages=document.pages,
            tags=[tag.tag for tag in document.tags],
            sections=[self._to_section(section) for section in document.sections],
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
