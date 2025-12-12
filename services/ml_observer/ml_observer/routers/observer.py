from __future__ import annotations

from typing import AsyncGenerator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status

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
