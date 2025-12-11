from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status

from document_service.core.repository import InMemoryRepository
from document_service.schemas import DocumentDetail, DocumentItem, DocumentSection, StatusUpdateRequest

router = APIRouter(prefix="/internal/documents", tags=["documents"])


def get_repository(request: Request) -> InMemoryRepository:
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise RuntimeError("Repository is not initialized")
    return repo


def get_tenant_id(request: Request) -> str:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Tenant-ID header")
    return tenant_id


@router.get("", response_model=List[DocumentItem])
async def list_documents(
    request: Request,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    product: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    repo: InMemoryRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> List[DocumentItem]:
    filters = {
        "status": status_filter,
        "product": product,
        "tag": tag,
        "search": search,
    }
    cleaned = {k: v for k, v in filters.items() if v}
    return repo.list_documents(tenant_id, cleaned)


@router.get("/{doc_id}", response_model=DocumentDetail)
async def get_document(
    doc_id: str,
    repo: InMemoryRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentDetail:
    document = repo.get_document(doc_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    return document


@router.get("/{doc_id}/sections/{section_id}", response_model=DocumentSection)
async def get_section(
    doc_id: str,
    section_id: str,
    repo: InMemoryRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentSection:
    document = repo.get_document(doc_id)
    if not document or document.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    section = repo.get_section(doc_id, section_id)
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
    return section


@router.post("/status", response_model=DocumentItem)
async def update_status(
    payload: StatusUpdateRequest = Body(...),
    repo: InMemoryRepository = Depends(get_repository),
) -> DocumentItem:
    try:
        return repo.update_status(payload.doc_id, payload.status, payload.error)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
