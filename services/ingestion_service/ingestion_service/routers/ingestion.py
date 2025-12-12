import uuid

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from ingestion_service.config import Settings
from ingestion_service.core.jobs import InMemoryJobStore
from ingestion_service.core.storage import StorageClient
from ingestion_service.schemas import EnqueueResponse, StatusPayload

router = APIRouter(prefix="/internal/ingestion", tags=["ingestion"])


def get_jobs(request: Request) -> InMemoryJobStore:
    jobs = getattr(request.app.state, "jobs", None)
    if jobs is None:
        raise RuntimeError("Job store is not initialized")
    return jobs


def get_storage(request: Request) -> StorageClient:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise RuntimeError("Storage client is not initialized")
    return storage


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        raise RuntimeError("Settings are not available")
    return settings


def get_tenant_id(request: Request) -> str:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Tenant-ID header")
    return tenant_id


@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue_document(
    file: UploadFile = File(...),
    product: str | None = Form(None),
    version: str | None = Form(None),
    tags: str | None = Form(None),
    jobs: InMemoryJobStore = Depends(get_jobs),
    storage: StorageClient = Depends(get_storage),
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> EnqueueResponse:
    content = await file.read()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    storage_uri = storage.upload(tenant_id, file.filename, content)
    ticket = jobs.create_job(doc_id)
    ticket.storage_uri = storage_uri

    # опциональная регистрация документа в Document Service
    if settings.doc_service_base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{settings.doc_service_base_url}/internal/documents",
                    json={
                        "doc_id": doc_id,
                        "tenant_id": tenant_id,
                        "name": file.filename,
                        "product": product,
                        "version": version,
                        "status": "uploaded",
                        "storage_uri": storage_uri,
                        "tags": (tags.split(",") if tags else []),
                    },
                )
        except Exception:
            # Логируем, но не падаем
            pass

    return EnqueueResponse(
        job_id=ticket.job_id,
        doc_id=ticket.doc_id,
        status=ticket.status,
        storage_uri=storage_uri,
    )


@router.post("/status", response_model=EnqueueResponse)
async def update_status(
    payload: StatusPayload,
    jobs: InMemoryJobStore = Depends(get_jobs),
    settings: Settings = Depends(get_settings),
) -> EnqueueResponse:
    try:
        ticket = jobs.update(payload.job_id, status=payload.status, error=payload.error)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")

    if settings.doc_service_base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{settings.doc_service_base_url}/internal/documents/status",
                    json={
                        "doc_id": ticket.doc_id,
                        "status": payload.status,
                        "error": payload.error,
                        "storage_uri": ticket.storage_uri,
                    },
                )
        except Exception:
            pass

    return EnqueueResponse(
        job_id=ticket.job_id,
        doc_id=ticket.doc_id,
        status=ticket.status,
        storage_uri=ticket.storage_uri,
    )
