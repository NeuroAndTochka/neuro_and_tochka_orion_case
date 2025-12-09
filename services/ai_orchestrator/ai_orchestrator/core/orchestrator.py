from __future__ import annotations

import time
from typing import Dict

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.clients.llm import LLMClient
from ai_orchestrator.clients.retrieval import RetrievalClient
from ai_orchestrator.clients.safety import SafetyClient
from ai_orchestrator.config import Settings
from ai_orchestrator.core.context_builder import build_context
from ai_orchestrator.schemas import OrchestratorRequest, OrchestratorResponse, SafetyBlock, SourceItem, Telemetry


class Orchestrator:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.retrieval = RetrievalClient(settings, http_client)
        self.llm = LLMClient(settings, http_client)
        self.safety = SafetyClient(settings, http_client)

    async def respond(self, request: OrchestratorRequest) -> OrchestratorResponse:
        trace_id = request.trace_id or "trace-unknown"
        retrieval_start = time.perf_counter()
        retrieval_chunks = await self.retrieval.search({"query": request.query, "tenant_id": request.user.tenant_id})
        retrieval_latency = int((time.perf_counter() - retrieval_start) * 1000)
        context = build_context(retrieval_chunks, self.settings.prompt_token_budget)
        llm_payload = self._build_llm_payload(request, context)
        llm_start = time.perf_counter()
        llm_result = await self.llm.generate(llm_payload)
        llm_latency = int((time.perf_counter() - llm_start) * 1000)
        safety_result = await self.safety.check_output({"answer": llm_result.get("answer", "")})
        if safety_result.get("status") not in {"allowed", "sanitized"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "OUTPUT_BLOCKED"})
        sources = [SourceItem(**src) for src in llm_result.get("sources", [])]
        telemetry = Telemetry(
            trace_id=trace_id,
            retrieval_latency_ms=retrieval_latency,
            llm_latency_ms=llm_latency,
            tool_steps=llm_result.get("meta", {}).get("tool_steps", 0),
        )
        safety_block = SafetyBlock(input="allowed", output=safety_result.get("status"))
        return OrchestratorResponse(answer=llm_result.get("answer", ""), sources=sources, safety=safety_block, telemetry=telemetry)

    def _build_llm_payload(self, request: OrchestratorRequest, context: list[Dict[str, str]]) -> Dict:
        return {
            "mode": "rag",
            "system_prompt": "You are Visior",
            "messages": [{"role": "user", "content": request.query}],
            "context_chunks": context,
            "generation_params": {"max_tokens": 512},
            "trace_id": request.trace_id,
        }
