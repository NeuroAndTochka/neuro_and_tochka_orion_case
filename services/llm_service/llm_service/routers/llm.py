from typing import Any, Dict

from fastapi import APIRouter, Depends, Request

from llm_service.core.orchestrator import LLMOrchestrator
from llm_service.schemas import GenerateRequest, GenerateResponse

router = APIRouter(prefix="/internal/llm", tags=["llm"])


def get_orchestrator(request: Request) -> LLMOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise RuntimeError("LLM orchestrator is not initialized")
    return orchestrator


@router.post("/generate")
async def generate(
    payload: Dict[str, Any],
    orchestrator: LLMOrchestrator = Depends(get_orchestrator),
):
    # If payload looks like OpenAI chat, proxy it; otherwise, treat as legacy GenerateRequest
    if "model" in payload and "messages" in payload and "system_prompt" not in payload:
        return await orchestrator.chat_proxy(payload)
    request = GenerateRequest(**payload)
    return await orchestrator.generate(request)


@router.get("/config")
async def get_config(request: Request):
    settings = getattr(request.app.state, "settings", None)
    if not settings:
        raise RuntimeError("Settings not configured")
    return {
        "default_model": settings.default_model,
        "max_tool_steps": settings.max_tool_steps,
        "enable_json_mode": settings.enable_json_mode,
        "mock_mode": settings.mock_mode,
        "llm_runtime_url": settings.llm_runtime_url,
    }


@router.post("/config")
async def update_config(payload: dict, request: Request):
    settings = getattr(request.app.state, "settings", None)
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if not settings:
        raise RuntimeError("Settings not configured")
    for field in [
        "default_model",
        "max_tool_steps",
        "enable_json_mode",
        "mock_mode",
        "llm_runtime_url",
        "runtime_api_key",
    ]:
        if field in payload and payload[field] is not None:
            setattr(settings, field, payload[field])
            if orchestrator:
                setattr(orchestrator.settings, field, payload[field])
    return await get_config(request)
