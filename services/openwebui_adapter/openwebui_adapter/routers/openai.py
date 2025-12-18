from __future__ import annotations

import json
import time
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse

from openwebui_adapter.clients.gateway import GatewayClient
from openwebui_adapter.config import Settings, get_settings
from openwebui_adapter.logging import get_logger
from openwebui_adapter.schemas import (
    AssistantContext,
    ChatCompletionRequest,
    ChatCompletionResponse,
    GatewayAssistantRequest,
    ModelsResponse,
)
from openwebui_adapter.utils import build_query_from_messages, chunk_answer, derive_conversation_id

router = APIRouter()
logger = get_logger(__name__)


async def get_gateway_client(request: Request) -> GatewayClient:
    return request.app.state.gateway_client


@router.get("/v1/models", response_model=ModelsResponse)
async def list_models(settings: Settings = Depends(get_settings)) -> ModelsResponse:
    return ModelsResponse(data=[{"id": settings.default_model_id, "object": "model"}])


@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
    response: Response,
    gateway_client: GatewayClient = Depends(get_gateway_client),
    settings: Settings = Depends(get_settings),
):
    try:
        auth_header = _resolve_auth_header(request.headers.get("authorization"), settings)
        query = build_query_from_messages(payload.messages, max_prefix_chars=settings.max_prefix_chars)
        conversation_id = derive_conversation_id(request.headers.get("x-conversation-id"), payload, request.headers.get("authorization"))
        if payload.model != settings.default_model_id:
            logger.warning("model.override", requested=payload.model, default=settings.default_model_id)
        gateway_payload = GatewayAssistantRequest(
            query=query,
            language=payload.language or settings.default_language,
            context=AssistantContext(channel="openwebui", conversation_id=conversation_id),
        )
        gw_response = await gateway_client.query(gateway_payload, auth_header)
    except HTTPException as exc:
        return _openai_error_response(
            message=_detail_to_message(exc.detail),
            status_code=exc.status_code,
            code=_error_code_for_status(exc.status_code),
            trace_id=uuid4().hex,
        )

    gw_body: Dict[str, Any] = {}
    try:
        gw_body = gw_response.json()
    except ValueError:
        gw_body = {}
    trace_id = _extract_trace_id(gw_body) or uuid4().hex

    if gw_response.status_code == status.HTTP_200_OK:
        answer = gw_body.get("answer", "")
        response.headers["X-Trace-Id"] = trace_id
        if payload.stream:
            return _streaming_response(answer, payload.model, trace_id, settings, gw_body.get("sources", []))
        completion = _build_completion_response(answer, payload.model, trace_id, gw_body.get("sources", []))
        logger.info("completion.success", trace_id=trace_id, stream=payload.stream)
        return completion

    if gw_response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
        return _openai_error_response(
            message="Authentication failed for Gateway",
            status_code=gw_response.status_code,
            code="authentication_error",
            trace_id=trace_id,
        )

    if gw_response.status_code == status.HTTP_400_BAD_REQUEST:
        details = gw_body.get("detail") or gw_body
        return _openai_error_response(
            message=_detail_to_message(details),
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_request_error",
            trace_id=trace_id,
            details=details,
        )

    return _openai_error_response(
        message="Gateway error",
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="bad_gateway",
        trace_id=trace_id,
        details=gw_body or None,
    )


def _resolve_auth_header(incoming: str | None, settings: Settings) -> str | None:
    if settings.auth_mode == "static_token":
        token = settings.static_bearer_token
        if not token:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="STATIC_BEARER_TOKEN is required for static_token mode")
        if token.lower().startswith("bearer "):
            return token
        return f"Bearer {token}"

    if settings.auth_mode == "passthrough":
        if not incoming:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
        return incoming

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unsupported AUTH_MODE")


def _build_completion_response(answer: str, model: str, trace_id: str | None, sources: list[dict[str, Any]] | None) -> ChatCompletionResponse:
    created = int(time.time())
    completion_id = f"chatcmpl-{trace_id or uuid4().hex[:12]}"
    message_payload: Dict[str, Any] = {"role": "assistant", "content": answer}
    if sources:
        message_payload["metadata"] = {"sources": sources, "trace_id": trace_id}
    response = ChatCompletionResponse(
        id=completion_id,
        created=created,
        model=model,
        choices=[{"index": 0, "message": message_payload, "finish_reason": "stop"}],
        usage={"prompt_tokens": 0, "completion_tokens": len(answer), "total_tokens": len(answer)},
    )
    return response


def _streaming_response(answer: str, model: str, trace_id: str | None, settings: Settings, sources: list[dict[str, Any]] | None):
    created = int(time.time())
    completion_id = f"chatcmpl-{trace_id or uuid4().hex[:12]}"
    chunks = chunk_answer(answer, settings.stream_chunk_chars)

    async def iterator():
        for idx, part in enumerate(chunks):
            finish_reason = "stop" if idx == len(chunks) - 1 else None
            payload = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": part} if part else {},
                        "finish_reason": finish_reason,
                    }
                ],
            }
            if sources and finish_reason:
                payload["choices"][0]["delta"]["metadata"] = {"sources": sources, "trace_id": trace_id}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    headers = {"X-Trace-Id": trace_id or ""}
    logger.info("completion.stream", trace_id=trace_id, chunks=len(chunks))
    return StreamingResponse(iterator(), media_type="text/event-stream", headers=headers)


def _detail_to_message(detail: Any) -> str:
    if isinstance(detail, dict):
        return detail.get("message") or detail.get("reason") or detail.get("code") or "Request rejected"
    return str(detail)


def _extract_trace_id(body: Dict[str, Any]) -> str | None:
    if not body:
        return None
    if isinstance(body.get("meta"), dict):
        meta_trace = body["meta"].get("trace_id")
        if meta_trace:
            return meta_trace
    if isinstance(body.get("detail"), dict):
        detail_trace = body["detail"].get("trace_id")
        if detail_trace:
            return detail_trace
    return None


def _openai_error_response(message: str, status_code: int, code: str | None = None, trace_id: str | None = None, details: Any = None):
    error_body: Dict[str, Any] = {
        "message": message,
        "type": _error_type_for_status(status_code),
    }
    if code:
        error_body["code"] = code
    if details is not None:
        error_body["details"] = details
    if trace_id:
        error_body["trace_id"] = trace_id
    headers = {"X-Trace-Id": trace_id} if trace_id else None
    return JSONResponse(status_code=status_code, content={"error": error_body}, headers=headers)


def _error_type_for_status(status_code: int) -> str:
    if status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}:
        return "authentication_error"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "invalid_request_error"
    if status_code in {status.HTTP_504_GATEWAY_TIMEOUT, status.HTTP_502_BAD_GATEWAY}:
        return "server_error"
    return "request_error"


def _error_code_for_status(status_code: int) -> str:
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "authentication_error"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "invalid_request_error"
    return "server_error"
