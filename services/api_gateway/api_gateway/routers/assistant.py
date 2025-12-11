from fastapi import APIRouter, Depends, HTTPException, status

from api_gateway.clients.orchestrator import OrchestratorClient
from api_gateway.clients.safety import SafetyClient
from api_gateway.core.context import AuthenticatedUser, get_request_context
from api_gateway.core.rate_limit import RateLimiter
from api_gateway.dependencies import (
    get_current_user,
    get_orchestrator_client,
    get_rate_limiter,
    get_safety_client,
)
from api_gateway.schemas import AssistantQueryRequest, AssistantResponse, AssistantResponseMeta, AssistantSource

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/query", response_model=AssistantResponse)
async def query_assistant(
    payload: AssistantQueryRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    safety_client: SafetyClient = Depends(get_safety_client),
    orchestrator_client: OrchestratorClient = Depends(get_orchestrator_client),
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> AssistantResponse:
    await rate_limiter.check(key=f"assistant:{user.tenant_id}:{user.user_id}")
    ctx = get_request_context()

    context_payload = None
    channel = None
    if payload.context:
        channel = payload.context.channel
        context_payload = payload.context.model_dump(exclude={"channel"}, exclude_none=True)

    safety_result = await safety_client.check_input(
        {
            "query": payload.query,
            "channel": channel,
            "context": context_payload or None,
            "meta": {"trace_id": ctx.trace_id},
            "user": {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "roles": user.roles,
            },
        }
    )
    if safety_result.get("status") not in {"allowed", "monitor"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "safety_blocked", "reason": safety_result.get("reason", "blocked by policy")},
        )

    downstream_payload = payload.model_dump()
    downstream_payload.update(
        {
            "trace_id": ctx.trace_id,
            "tenant_id": user.tenant_id,
            "user": {
                "user_id": user.user_id,
                "tenant_id": user.tenant_id,
                "roles": user.roles,
            },
            "safety": safety_result,
        }
    )

    orchestrator_response = await orchestrator_client.query(downstream_payload)

    sources = [AssistantSource(**src) for src in orchestrator_response.get("sources", [])]
    meta_payload = orchestrator_response.get("meta", {})
    meta = AssistantResponseMeta(
        latency_ms=meta_payload.get("latency_ms"),
        trace_id=meta_payload.get("trace_id", ctx.trace_id),
        safety=meta_payload.get("safety") or {"input": safety_result.get("status")},
    )
    answer = orchestrator_response.get("answer", "")

    return AssistantResponse(answer=answer, sources=sources, meta=meta)
