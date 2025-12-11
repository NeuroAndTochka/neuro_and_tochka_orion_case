from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from ingestion_service.core.storage import InMemoryQueue
from ingestion_service.schemas import EnqueueResponse, StatusPayload

router = APIRouter(prefix="/internal/ingestion", tags=["ingestion"])


def get_queue(request: Request) -> InMemoryQueue:
    queue = getattr(request.app.state, "queue", None)
    if queue is None:
        raise RuntimeError("Queue is not initialized")
    return queue


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
    queue: InMemoryQueue = Depends(get_queue),
    tenant_id: str = Depends(get_tenant_id),
) -> EnqueueResponse:
    content = await file.read()
    ticket = queue.enqueue(file.filename, tenant_id, content)
    return EnqueueResponse(job_id=ticket.job_id, doc_id=ticket.doc_id, status=ticket.status)


@router.post("/status", response_model=EnqueueResponse)
async def update_status(
    payload: StatusPayload,
    queue: InMemoryQueue = Depends(get_queue),
) -> EnqueueResponse:
    try:
        ticket = queue.update_status(payload.job_id, payload.status, payload.error)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job_not_found")
    return EnqueueResponse(job_id=ticket.job_id, doc_id=ticket.doc_id, status=ticket.status)
