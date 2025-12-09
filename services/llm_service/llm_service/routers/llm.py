from fastapi import APIRouter, Depends, Request

from llm_service.core.orchestrator import LLMOrchestrator
from llm_service.schemas import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/internal/llm", tags=["llm"])


def get_orchestrator(request: Request) -> LLMOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("LLM orchestrator is not initialized")
    return orchestrator


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    payload: GenerateRequest,
    orchestrator: LLMOrchestrator = Depends(get_orchestrator),
) -> GenerateResponse:
    return await orchestrator.generate(payload)
