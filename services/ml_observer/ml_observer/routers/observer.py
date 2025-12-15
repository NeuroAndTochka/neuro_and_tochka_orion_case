from __future__ import annotations

from typing import AsyncGenerator, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from ml_observer.config import Settings
from ml_observer.core.repository import ObserverRepository
from ml_observer.schemas import (
    DocumentStatus,
    DocumentUploadRequest,
    ExperimentCreateRequest,
    ExperimentDetail,
    LLMDryRunRequest,
    LLMDryRunResponse,
    RetrievalRunRequest,
    RetrievalRunResponse,
    RetrievalSearchRequest,
)

router = APIRouter(prefix="/internal/observer", tags=["observer"])


async def get_repository(request: Request) -> AsyncGenerator[ObserverRepository, None]:
    session_factory = getattr(request.app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError("Session factory is not configured")
    async with session_factory() as session:
        yield ObserverRepository(session)


def get_tenant_id(request: Request) -> str:
    tenant_id = request.headers.get("X-Tenant-ID")
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing X-Tenant-ID header")
    return tenant_id


def get_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise RuntimeError("Settings are not configured")
    return settings


@router.post("/experiments", response_model=ExperimentDetail, status_code=status.HTTP_201_CREATED)
async def create_experiment(
    payload: ExperimentCreateRequest,
    repo: ObserverRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> ExperimentDetail:
    experiment_id = uuid4().hex
    return await repo.create_experiment(
        experiment_id=experiment_id,
        tenant_id=tenant_id,
        name=payload.name,
        description=payload.description,
        params=payload.params,
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetail)
async def get_experiment(
    experiment_id: str,
    repo: ObserverRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> ExperimentDetail:
    experiment = await repo.get_experiment(experiment_id, tenant_id)
    if not experiment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment_not_found")
    return experiment


@router.post("/documents/upload", response_model=DocumentStatus, status_code=status.HTTP_201_CREATED)
async def upload_document(
    payload: DocumentUploadRequest,
    repo: ObserverRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentStatus:
    record_id = uuid4().hex
    return await repo.upsert_document(
        record_id=record_id,
        tenant_id=tenant_id,
        doc_id=payload.doc_id,
        name=payload.name,
        status="queued",
        storage_uri=payload.storage_uri,
        meta=payload.meta,
        experiment_id=payload.experiment_id,
    )


@router.get("/documents/{doc_id}", response_model=DocumentStatus)
async def get_document(
    doc_id: str,
    repo: ObserverRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentStatus:
    document = await repo.get_document(tenant_id, doc_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
    return document


@router.post("/ingestion/enqueue", response_model=DocumentStatus, status_code=status.HTTP_201_CREATED)
async def proxy_ingestion_enqueue(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentStatus:
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.ingestion_base_url}/internal/ingestion/enqueue",
                files={"file": (file.filename, await file.read(), file.content_type or "application/octet-stream")},
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            data = resp.json()
            return DocumentStatus(
                doc_id=data["doc_id"],
                status=data.get("status", "queued"),
                storage_uri=data.get("storage_uri"),
                experiment_id=None,
                meta={"job_id": data.get("job_id")},
            )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/ingestion/status", response_model=DocumentStatus)
async def proxy_ingestion_status(
    payload: dict,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
) -> DocumentStatus:
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    job_id = payload.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id required")
    override_status = payload.get("status")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if override_status:
                resp = await client.post(
                    f"{settings.ingestion_base_url}/internal/ingestion/status",
                    json={"job_id": job_id, "status": override_status},
                    headers={"X-Tenant-ID": tenant_id},
                )
                resp.raise_for_status()
            job_resp = await client.get(
                f"{settings.ingestion_base_url}/internal/ingestion/jobs/{job_id}",
                headers={"X-Tenant-ID": tenant_id},
            )
            job_resp.raise_for_status()
            data = job_resp.json()
            return DocumentStatus(
                doc_id=data["doc_id"],
                status=data.get("status"),
                storage_uri=data.get("storage_uri"),
                experiment_id=None,
                meta={"job_id": job_id, "logs": data.get("logs", []), "error": data.get("error")},
            )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/documents")
async def list_documents(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.document_base_url:
        raise HTTPException(status_code=503, detail="document_service_not_configured")
    params = {"status": status_filter, "limit": limit, "offset": offset}
    params = {k: v for k, v in params.items() if v is not None}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.document_base_url}/internal/documents",
                params=params,
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/summarizer/config")
async def get_summarizer_config(
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.ingestion_base_url}/internal/ingestion/summarizer/config",
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/summarizer/config")
async def update_summarizer_config(
    payload: dict,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ingestion_base_url}/internal/ingestion/summarizer/config",
                json=payload,
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/chunking/config")
async def get_chunking_config(
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.ingestion_base_url}/internal/ingestion/chunking/config",
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chunking/config")
async def update_chunking_config(
    payload: dict,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.ingestion_base_url}/internal/ingestion/chunking/config",
                json=payload,
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/documents/{doc_id}/tree")
async def get_document_tree(
    doc_id: str,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.ingestion_base_url:
        raise HTTPException(status_code=503, detail="ingestion_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.ingestion_base_url}/internal/ingestion/documents/{doc_id}/tree",
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/documents/{doc_id}/detail")
async def get_document_detail(
    doc_id: str,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.document_base_url:
        raise HTTPException(status_code=503, detail="document_service_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.document_base_url}/internal/documents/{doc_id}",
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/retrieval/run", response_model=RetrievalRunResponse, status_code=status.HTTP_201_CREATED)
async def run_retrieval(
    payload: RetrievalRunRequest,
    repo: ObserverRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> RetrievalRunResponse:
    run_id = uuid4().hex
    hits, metrics = repo.build_mock_hits(payload.queries, payload.top_k)
    summary = await repo.add_run(
        run_id=run_id,
        tenant_id=tenant_id,
        run_type="retrieval",
        status="completed",
        payload=payload.model_dump(),
        result={"hits": [hit.model_dump() for hit in hits]},
        metrics=metrics,
        experiment_id=payload.experiment_id,
    )
    return RetrievalRunResponse(run_id=summary.run_id, status=summary.status, hits=hits, metrics=metrics)


@router.post("/llm/dry-run", response_model=LLMDryRunResponse, status_code=status.HTTP_201_CREATED)
async def llm_dry_run(
    payload: LLMDryRunRequest,
    repo: ObserverRepository = Depends(get_repository),
    tenant_id: str = Depends(get_tenant_id),
) -> LLMDryRunResponse:
    run_id = uuid4().hex
    answer = "Mock LLM answer based on provided prompt and context."
    usage = {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
    await repo.add_run(
        run_id=run_id,
        tenant_id=tenant_id,
        run_type="llm",
        status="completed",
        payload=payload.model_dump(),
        result={"answer": answer, "usage": usage},
        metrics={},
        experiment_id=payload.experiment_id,
    )
    return LLMDryRunResponse(
        run_id=run_id,
        status="completed",
        answer=answer,
        usage=usage,
        metadata=payload.metadata,
    )


@router.post("/retrieval/search")
async def retrieval_search(
    payload: RetrievalSearchRequest,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.retrieval_base_url:
        raise HTTPException(status_code=503, detail="retrieval_not_configured")
    body = {
        "query": payload.query,
        "tenant_id": tenant_id,
        "max_results": payload.max_results,
        "filters": payload.filters,
        "doc_ids": payload.doc_ids,
        "section_ids": payload.section_ids,
        "trace_id": payload.trace_id,
        "rerank_enabled": payload.rerank_enabled,
    }
    try:
        timeout = 45.0 if payload.rerank_enabled else 10.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{settings.retrieval_base_url}/internal/retrieval/search", json=body)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/retrieval/config")
async def get_retrieval_config(
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.retrieval_base_url:
        raise HTTPException(status_code=503, detail="retrieval_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.retrieval_base_url}/internal/retrieval/config",
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/retrieval/config")
async def update_retrieval_config(
    payload: dict,
    settings: Settings = Depends(get_settings),
    tenant_id: str = Depends(get_tenant_id),
):
    if not settings.retrieval_base_url:
        raise HTTPException(status_code=503, detail="retrieval_not_configured")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.retrieval_base_url}/internal/retrieval/config",
                json=payload,
                headers={"X-Tenant-ID": tenant_id},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
