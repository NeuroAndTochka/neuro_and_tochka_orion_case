from __future__ import annotations

from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from document_service.core.repository import DocumentRepository
from document_service.schemas import (
    DocumentCreateRequest,
    DocumentDetail,
    DocumentListResponse,
    DocumentSection,
    DownloadUrlResponse,
    SectionsUpsertRequest,
    StatusUpdateRequest,
)
from document_service.storage import StorageClient

router = APIRouter(prefix="/internal/documents", tags=["documents"])


async def get_repository(request: Request) -> AsyncGenerator[DocumentRepository, None]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("Session factory is not configured")
    async with session_factory() as session:
        yield DocumentRepository(session)


def get_storage_client(request: Request) -> StorageClient:
    storage = getattr(request.app.state, "storage_client", None)
    if storage is None:
        raise RuntimeError("Storage client is not configured")
    return storage


def get_tenant_id(request: Request) -> str:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Tenant-ID header")
    return tenant_id


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
async def create_document(
    payload: DocumentCreateRequest,
    repo: DocumentRepository = Depends(get_repository),
) -> DocumentDetail:
    try:
        return await repo.create_or_update_document(payload)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="document_forbidden")


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    product: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    repo: DocumentRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentListResponse:
    filters = {
        "status": status_filter,
        "product": product,
        "tag": tag,
        "search": search,
    }
    cleaned = {k: v for k, v in filters.items() if v}
    total, items = await repo.list_documents(tenant_id, cleaned, limit, offset)
    return DocumentListResponse(total=total, items=items)


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    repo: DocumentRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentDetail:
    document = await repo.get_document(doc_id, tenant_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    return document


@router.get("/{doc_id}/sections/{section_id}", response_model=DocumentSection)
async def get_section(
    doc_id: str,
    section_id: str,
    repo: DocumentRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentSection:
    section = await repo.get_section(doc_id, section_id, tenant_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
    return section


@router.post("/{doc_id}/sections", response_model=DocumentDetail)
async def upsert_sections(
    doc_id: str,
    payload: SectionsUpsertRequest,
    repo: DocumentRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentDetail:
    document = await repo.upsert_sections(doc_id, tenant_id, payload.sections)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    return document


@router.post("/status", response_model=DocumentDetail)
async def update_status(
    payload: StatusUpdateRequest = Body(...),
    repo: DocumentRepository = Depends(get_repository),
) -> DocumentDetail:
    tenant_id = await repo.update_status(payload)
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    document = await repo.get_document(payload.doc_id, tenant_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    return document


@router.get("/{doc_id}/download-url", response_model=DownloadUrlResponse)
async def get_download_url(
    doc_id: str,
    repo: DocumentRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
    storage: StorageClient = Depends(get_storage_client),
) -> DownloadUrlResponse:
    detail = await repo.get_document(doc_id, tenant_id)
    if not detail or not detail.storage_uri:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="storage_not_found")
    try:
        url = storage.generate_download_url(detail.storage_uri)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return DownloadUrlResponse(doc_id=doc_id, url=url, expires_in=storage.default_expiry)
