from fastapi import APIRouter, Depends, Request

from ai_orchestrator.core.orchestrator import Orchestrator
from ai_orchestrator.schemas import OrchestratorRequest, OrchestratorResponse

router = APIRouter(prefix="/internal/orchestrator", tags=["orchestrator"])


def get_orchestrator(request: Request) -> Orchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("Orchestrator is not initialized")
    return orchestrator


@router.post("/respond", response_model=OrchestratorResponse)
async def respond(
    payload: OrchestratorRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> OrchestratorResponse:
    return await orchestrator.respond(payload)
