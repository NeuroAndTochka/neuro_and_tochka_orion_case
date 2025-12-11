from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import httpx
from fastapi import HTTPException, status

from llm_service.clients.mcp import MCPClient
from llm_service.clients.runtime import LLMRuntimeClient, LLMRuntimeResult
from llm_service.config import Settings
from llm_service.core.prompt import build_rag_prompt
from llm_service.schemas import GenerateRequest, GenerateResponse, ToolCallTrace, UsageStats


@dataclass
class ToolState:
    traces: List[ToolCallTrace] = field(default_factory=list)
    steps: int = 0


class LLMOrchestrator:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.runtime = LLMRuntimeClient(settings, http_client)
        self.mcp = MCPClient(settings, http_client)

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        trace_id = request.trace_id or "trace-unknown"
        messages = build_rag_prompt(request.system_prompt, request.messages, request.context_chunks)
        context_payload = [chunk.model_dump() for chunk in request.context_chunks]
        usage = UsageStats()
        tool_state = ToolState()

        for _ in range(self.settings.max_tool_steps + 1):
            payload = self._build_runtime_payload(messages, context_payload, request)
            result = await self.runtime.chat_completion(payload)
            usage.prompt += result.usage.get("prompt_tokens", 0)
            usage.completion += result.usage.get("completion_tokens", 0)

            if result.type == "message":
                meta = {
                    "model_name": self.settings.default_model,
                    "trace_id": trace_id,
                    "tool_steps": tool_state.steps,
                }
                return GenerateResponse(answer=result.content or "", used_tokens=usage, tools_called=tool_state.traces, meta=meta)

            if result.type == "tool_call":
                tool_state.steps += 1
                if tool_state.steps > self.settings.max_tool_steps:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"code": "LLM_LIMIT_EXCEEDED", "message": "Tool-call limit reached"},
                    )
                tool_result = await self._execute_tool(result, request, trace_id)
                tool_state.traces.append(
                    ToolCallTrace(
                        name=result.tool_name or "unknown",
                        arguments=result.tool_arguments or {},
                        result_summary=str(tool_result.get("result")),
                    )
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": f"TOOL_RESULT:{tool_result.get('result')}"
                        if tool_result.get("status") == "ok"
                        else f"TOOL_ERROR:{tool_result.get('error')}",
                    }
                )
                continue

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "LLM_LOOP", "message": "No final answer"})

    def _build_runtime_payload(
        self,
        messages: List[Dict[str, str]],
        context_payload: List[Dict[str, Any]],
        request: GenerateRequest,
    ) -> Dict[str, Any]:
        params = request.generation_params
        payload = {
            "model": self.settings.default_model,
            "messages": messages,
            "context": context_payload,
            "max_tokens": params.max_tokens or self.settings.max_completion_tokens,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "presence_penalty": params.presence_penalty,
            "frequency_penalty": params.frequency_penalty,
        }
        if params.stop:
            payload["stop"] = params.stop
        if self.settings.enable_json_mode:
            payload["response_format"] = {"type": "json_object"}
        return payload

    async def _execute_tool(self, result: LLMRuntimeResult, request: GenerateRequest, trace_id: str) -> Dict[str, Any]:
        tool_name = result.tool_name or "unknown"
        arguments = result.tool_arguments or {}
        user_claim = {"user_id": "llm", "tenant_id": "tenant"}
        return await self.mcp.execute(tool_name, arguments, user_claim, trace_id)
