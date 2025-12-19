from typing import Any, Dict

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
    payload: Dict[str, Any],
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> OrchestratorResponse:
    request = OrchestratorRequest(**payload)
    return await orchestrator.respond(request)


@router.get("/config")
async def get_config(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise RuntimeError("Settings not configured")
    return {
        "default_model": settings.default_model,
        "model_strategy": settings.model_strategy,
        "prompt_token_budget": settings.prompt_token_budget,
        "context_token_budget": settings.context_token_budget,
        "max_tool_steps": settings.max_tool_steps,
        "window_radius": settings.window_radius,
        # legacy knobs preserved for backward compatibility, mapped to the unified radius
        "window_initial": settings.window_initial,
        "window_step": settings.window_step,
        "window_max": settings.window_max,
        "mock_mode": settings.mock_mode,
    }


@router.post("/config")
async def update_config(payload: dict, request: Request):
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise RuntimeError("Settings not configured")
    for field in ["default_model", "prompt_token_budget", "context_token_budget", "max_tool_steps", "mock_mode", "model_strategy"]:
        if field in payload and payload[field] is not None:
            setattr(settings, field, payload[field])
    # Unify legacy knobs into the single radius parameter
    radius = payload.get("window_radius")
    legacy_window_max = payload.get("window_max")
    if radius is None and legacy_window_max is not None:
        radius = legacy_window_max
    legacy_total = payload.get("max_chunk_window") or payload.get("max_chunk_window_total")
    if radius is None and legacy_total is not None:
        radius = max(0, (int(legacy_total) - 1) // 2)
    if radius is not None:
        max_allowed = getattr(settings, "window_radius_baseline", settings.window_radius)
        settings.window_radius = min(max(0, int(radius)), max_allowed)
        settings.window_max = settings.window_radius
        settings.window_initial = min(settings.window_initial or (1 if settings.window_radius > 0 else 0), settings.window_radius)
        settings.window_step = min(settings.window_step or 1, settings.window_radius or 1)
    return await get_config(request)
