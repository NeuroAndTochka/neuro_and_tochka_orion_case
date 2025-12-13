import uuid
from datetime import datetime

import httpx
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from ingestion_service.config import Settings
from ingestion_service.core.jobs import JobRecord, JobStore
from ingestion_service.core.pipeline import process_file
from ingestion_service.core.storage import StorageClient
from ingestion_service.core.embedding import EmbeddingClient
from ingestion_service.core.summarizer import Summarizer
from ingestion_service.core.vector_store import VectorStore
from ingestion_service.schemas import (
    EnqueueResponse,
    JobStatusResponse,
    StatusPayload,
    SummarizerConfig,
)

router = APIRouter(prefix="/internal/ingestion", tags=["ingestion"])


def get_jobs(request: Request) -> JobStore:
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


def get_embedding_client(request: Request) -> EmbeddingClient:
    client = getattr(request.app.state, "embedding_client", None)
    if client is None:
        raise RuntimeError("Embedding client is not configured")
    return client


def get_vector_store(request: Request) -> VectorStore:
    store = getattr(request.app.state, "vector_store", None)
    if store is None:
        raise RuntimeError("Vector store is not configured")
    return store


def get_summarizer(request: Request) -> Summarizer:
    client = getattr(request.app.state, "summarizer", None)
    if client is None:
        raise RuntimeError("Summarizer is not configured")
    return client


def get_tenant_id(request: Request) -> str:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Tenant-ID header"
        )
    return tenant_id


@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue_document(
    file: UploadFile = File(...),
    product: str | None = Form(None),
    version: str | None = Form(None),
    tags: str | None = Form(None),
    jobs: JobStore = Depends(get_jobs),
    storage: StorageClient = Depends(get_storage),
    settings: Settings = Depends(get_settings),
    embedding: EmbeddingClient = Depends(get_embedding_client),
    summarizer: Summarizer = Depends(get_summarizer),
    vector_store: VectorStore = Depends(get_vector_store),
    tenant_id: str = Depends(get_tenant_id),
    background: BackgroundTasks = None,
) -> EnqueueResponse:
    content = await file.read()
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"
    storage_uri = storage.upload(tenant_id, file.filename, content)
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    ticket = jobs.create(
        JobRecord(
            job_id=job_id,
            tenant_id=tenant_id,
            doc_id=doc_id,
            status="queued",
            submitted_at=datetime.utcnow(),
            storage_uri=storage_uri,
            error=None,
        )
    )

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

    if background is not None:
        background.add_task(
            process_file,
            ticket=ticket,
            storage=storage,
            embedding=embedding,
            summarizer=summarizer,
            jobs=jobs,
            doc_service_base_url=settings.doc_service_base_url,
            max_pages=settings.max_pages,
            max_file_mb=settings.max_file_mb,
            chunk_size=settings.chunk_size,
            vector_store=vector_store,
        )

    return EnqueueResponse(
        job_id=ticket.job_id,
        tenant_id=ticket.tenant_id,
        doc_id=ticket.doc_id,
        status=ticket.status,
        storage_uri=storage_uri,
    )


@router.post("/status", response_model=EnqueueResponse)
async def update_status(
    payload: StatusPayload,
    jobs: JobStore = Depends(get_jobs),
    settings: Settings = Depends(get_settings),
) -> EnqueueResponse:
    try:
        ticket = jobs.update(payload.job_id, status=payload.status, error=payload.error)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found"
        )

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
                    headers={"X-Tenant-ID": ticket.tenant_id},
                )
        except Exception:
            pass

    return EnqueueResponse(
        job_id=ticket.job_id,
        tenant_id=ticket.tenant_id,
        doc_id=ticket.doc_id,
        status=ticket.status,
        storage_uri=ticket.storage_uri,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    jobs: JobStore = Depends(get_jobs),
) -> JobStatusResponse:
    ticket = jobs.get(job_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found"
        )
    logs = jobs.get_logs(job_id)
    return JobStatusResponse(
        job_id=ticket.job_id,
        tenant_id=ticket.tenant_id,
        doc_id=ticket.doc_id,
        status=ticket.status,
        storage_uri=ticket.storage_uri,
        error=ticket.error,
        logs=logs,
    )


@router.get("/summarizer/config", response_model=SummarizerConfig)
async def get_summarizer_config(
    summarizer: Summarizer = Depends(get_summarizer),
) -> SummarizerConfig:
    return SummarizerConfig(**summarizer.get_config())


@router.post("/summarizer/config", response_model=SummarizerConfig)
async def update_summarizer_config(
    payload: SummarizerConfig, summarizer: Summarizer = Depends(get_summarizer)
) -> SummarizerConfig:
    updated = summarizer.update_config(
        system_prompt=payload.system_prompt,
        model=payload.model,
        max_tokens=payload.max_tokens,
        use_roles=payload.use_roles,
    )
    return SummarizerConfig(**updated)


@router.get("/documents/{doc_id}/tree")
async def get_document_tree(
    doc_id: str,
    vector_store: VectorStore = Depends(get_vector_store),
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.doc_service_base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="document_service_not_configured",
        )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.doc_service_base_url}/internal/documents/{doc_id}",
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            detail = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.text
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    chunks_meta = vector_store.get_chunks(doc_id, tenant_id) if vector_store else []
    chunk_map = {}
    for meta in chunks_meta:
        cid = meta.get("chunk_id")
        if not cid and isinstance(meta.get("id"), str) and ":" in meta["id"]:
            cid = meta["id"].split(":", 1)[1]
        chunk_map[cid] = meta

    sections = []
    for sec in detail.get("sections", []):
        sec_chunks = []
        for cid in sec.get("chunk_ids") or []:
            meta = chunk_map.get(cid, {})
            sec_chunks.append(
                {
                    "chunk_id": cid,
                    "text": meta.get("text"),
                    "score": meta.get("score"),
                }
            )
        section_copy = dict(sec)
        section_copy["chunks"] = sec_chunks
        sections.append(section_copy)

    return {
        "doc_id": detail.get("doc_id"),
        "name": detail.get("name"),
        "status": detail.get("status"),
        "storage_uri": detail.get("storage_uri"),
        "pages": detail.get("pages"),
        "sections": sections,
        "tags": detail.get("tags", []),
    }
