from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.clients.mcp import MCPClient
from ai_orchestrator.clients.retrieval import RetrievalClient
from ai_orchestrator.clients.runtime import LLMRuntimeClient, RuntimeResult
from ai_orchestrator.config import Settings
from ai_orchestrator.core.context_builder import build_context
from ai_orchestrator.logging import get_logger
from ai_orchestrator.schemas import (
    OrchestratorRequest,
    OrchestratorResponse,
    SafetyBlock,
    SourceItem,
    Telemetry,
    ToolCallTrace,
    UserContext,
)


class ProgressiveWindowState:
    def __init__(self, initial: int, step: int, max_window: int) -> None:
        self.initial = initial
        self.step = step
        self.max_window = max_window
        self.window_by_section: Dict[str, int] = {}
        self.tokens_used: int = 0

    def next_window(self, section_id: str) -> int:
        current = self.window_by_section.get(section_id, self.initial)
        self.window_by_section[section_id] = min(self.max_window, current + self.step)
        return current

    def add_tokens(self, tokens: int) -> None:
        self.tokens_used += max(0, tokens)


class Orchestrator:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.retrieval = RetrievalClient(settings, http_client)
        self.runtime = LLMRuntimeClient(settings, http_client)
        self.mcp = MCPClient(settings, http_client)
        self._logger = get_logger(__name__)

    async def respond(self, request: OrchestratorRequest) -> OrchestratorResponse:
        user_context = request.user
        if user_context is None:
            if request.user_id and request.tenant_id:
                user_context = UserContext(user_id=request.user_id, tenant_id=request.tenant_id)
            else:
                user_context = UserContext(user_id=self.settings.default_user_id, tenant_id=self.settings.default_tenant_id)
        if not user_context.tenant_id:
            user_context.tenant_id = self.settings.default_tenant_id

        trace_id = request.trace_id or "trace-unknown"
        self._logger.info(
            "orchestrator_request_received",
            trace_id=trace_id,
            tenant_id=user_context.tenant_id,
            query=request.query,
            source=request.channel or "ui",
        )
        retrieval_start = time.perf_counter()
        retrieval_hits, retrieval_steps = await self.retrieval.search(
            {
                "query": request.query,
                "tenant_id": user_context.tenant_id,
                "filters": request.filters,
                "doc_ids": request.doc_ids,
                "section_ids": request.section_ids,
                "max_results": request.max_results,
                "trace_id": trace_id,
            }
        )
        retrieval_latency = int((time.perf_counter() - retrieval_start) * 1000)
        steps_docs = retrieval_steps.get("docs", 0) if retrieval_steps else 0
        steps_sections = retrieval_steps.get("sections", 0) if retrieval_steps else 0
        steps_chunks = retrieval_steps.get("chunks", 0) if retrieval_steps else 0
        self._logger.info(
            "orchestrator_retrieval_result",
            trace_id=trace_id,
            tenant_id=user_context.tenant_id,
            hits=len(retrieval_hits),
            docs=steps_docs,
            sections=steps_sections,
            chunks=steps_chunks,
            latency_ms=retrieval_latency,
        )

        sections = self._select_sections(retrieval_hits)
        context = build_context(sections, self.settings.prompt_token_budget)
        section_chunk_map = self._build_section_chunk_index(sections)
        messages = self._build_messages(request.query, context)
        tools = self._tool_schemas()
        usage = {"prompt": 0, "completion": 0}
        window_state = ProgressiveWindowState(self.settings.window_initial, self.settings.window_step, self.settings.window_max)
        tool_traces: List[ToolCallTrace] = []

        for step in range(self.settings.max_tool_steps + 1):
            payload = {
                "model": "mock-model" if self.settings.mock_mode else self.settings.default_model,
                "messages": messages,
                "tools": tools,
                "context": context,
            }
            self._logger.info(
                "orchestrator_llm_request",
                trace_id=trace_id,
                tenant_id=user_context.tenant_id,
                model=payload["model"],
                empty_context=not bool(context),
                step=step,
            )
            try:
                result = await self.runtime.chat_completion(payload)
            except Exception as exc:
                self._logger.error(
                    "orchestrator_llm_request_failed",
                    trace_id=trace_id,
                    tenant_id=user_context.tenant_id,
                    error=str(exc),
                    step=step,
                    exc_info=True,
                )
                raise
            self._logger.info(
                "orchestrator_llm_response",
                trace_id=trace_id,
                tenant_id=user_context.tenant_id,
                response_type=result.type,
                tool_name=result.tool_name,
                prompt_tokens=result.usage.get("prompt_tokens", 0),
                completion_tokens=result.usage.get("completion_tokens", 0),
                step=step,
            )
            usage["prompt"] += result.usage.get("prompt_tokens", 0)
            usage["completion"] += result.usage.get("completion_tokens", 0)
            window_state.add_tokens(result.usage.get("prompt_tokens", 0))
            if window_state.tokens_used > self.settings.context_token_budget:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "CONTEXT_BUDGET_EXCEEDED", "message": "Context budget exceeded"},
                )

            if result.type == "message":
                telemetry = Telemetry(
                    trace_id=trace_id,
                    retrieval_latency_ms=retrieval_latency,
                    llm_latency_ms=None,
                    tool_steps=step,
                )
                safety_block = SafetyBlock(input="allowed", output="allowed")
                sources = self._build_sources(context)
                return OrchestratorResponse(
                    answer=result.content or "",
                    sources=sources,
                    tools=tool_traces,
                    safety=safety_block,
                    telemetry=telemetry,
                )

            if step >= self.settings.max_tool_steps:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "LLM_LIMIT_EXCEEDED", "message": "Tool-call limit reached"},
                )
            tool_name = result.tool_name or "unknown"
            arguments = result.tool_arguments or {}
            tool_result, tokens_used = await self._execute_tool(tool_name, arguments, section_chunk_map, window_state, user_context, trace_id)
            window_state.add_tokens(tokens_used)
            if window_state.tokens_used > self.settings.context_token_budget:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "CONTEXT_BUDGET_EXCEEDED", "message": "Context budget exceeded"},
                )
            tool_traces.append(ToolCallTrace(name=tool_name, arguments=arguments, result_summary=str(tool_result.get("result"))))
            messages.append(
                {
                    "role": "assistant",
                    "content": f"TOOL_RESULT:{json.dumps(tool_result)}",
                }
            )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "LLM_LOOP", "message": "No final answer"})

    def _select_sections(self, hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sections = [h for h in hits if h.get("section_id")]
        if sections:
            return sections
        return hits

    def _build_sources(self, context: List[Dict[str, Any]]) -> List[SourceItem]:
        sources = []
        for item in context:
            sources.append(
                SourceItem(
                    doc_id=item.get("doc_id", ""),
                    section_id=item.get("section_id"),
                    title=item.get("title"),
                    page_start=item.get("page_start"),
                    page_end=item.get("page_end"),
                    score=item.get("score"),
                )
            )
        return sources

    def _build_messages(self, query: str, context: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        context_block = json.dumps(
            [
                {
                    "doc_id": c.get("doc_id"),
                    "section_id": c.get("section_id"),
                    "summary": c.get("summary"),
                    "score": c.get("score"),
                    "pages": [c.get("page_start"), c.get("page_end")],
                }
                for c in context
            ],
            ensure_ascii=False,
        )
        system_msg = (
            "You are Visior. Think step by step and keep your chain-of-thought hidden from the user. "
            "You only have section summaries/metadata, not full text. "
            "Use tools to fetch raw text when unsure and verify claims. "
            "Cite sources as [doc_id/section_id]. Progressively expand windows if more text is needed."
        )
        developer_msg = (
            "Tool policy: reason internally first, then call MCP tools to confirm or gather evidence. "
            "Start with a small chunk window; if still unsure, expand gradually. "
            "Never expose chain-of-thought; return only the final answer with concise citations."
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "system", "content": developer_msg},
            {"role": "system", "content": f"Retrieved sections (summaries only): {context_block}"},
            {"role": "user", "content": query},
        ]

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_chunk_window",
                    "description": "Fetch a small window of text around a section's anchor chunk.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string"},
                            "section_id": {"type": "string"},
                            "anchor_chunk_id": {"type": "string"},
                            "window_before": {"type": "integer", "minimum": 0},
                            "window_after": {"type": "integer", "minimum": 0},
                        },
                        "required": ["doc_id", "section_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_doc_section",
                    "description": "Read a whole section if chunk window is unavailable.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "doc_id": {"type": "string"},
                            "section_id": {"type": "string"},
                        },
                        "required": ["doc_id", "section_id"],
                    },
                },
            },
        ]

    def _build_section_chunk_index(self, sections: List[Dict[str, Any]]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for sec in sections:
            sec_id = sec.get("section_id")
            chunk_ids = sec.get("chunk_ids") or []
            if isinstance(chunk_ids, list) and sec_id and chunk_ids:
                mapping[sec_id] = chunk_ids[0]
            elif sec_id and sec.get("chunk_id"):
                mapping[sec_id] = sec.get("chunk_id")
        return mapping

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        section_chunk_map: Dict[str, str],
        window_state: ProgressiveWindowState,
        user: UserContext,
        trace_id: str,
    ) -> Tuple[Dict[str, Any], int]:
        doc_id = str(arguments.get("doc_id") or "")
        section_id = str(arguments.get("section_id") or "")
        anchor_chunk_id = arguments.get("anchor_chunk_id") or section_chunk_map.get(section_id)
        window = window_state.next_window(section_id) if section_id else self.settings.window_initial
        window_before = int(arguments.get("window_before", window))
        window_after = int(arguments.get("window_after", window))

        if not doc_id or not section_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id and section_id required")

        args = {
            "doc_id": doc_id,
            "section_id": section_id,
        }
        tool_to_call = tool_name or "read_chunk_window"
        if anchor_chunk_id:
            tool_to_call = "read_chunk_window"
            args.update(
                {
                    "anchor_chunk_id": anchor_chunk_id,
                    "window_before": window_before,
                    "window_after": window_after,
                }
            )
        else:
            tool_to_call = "read_doc_section"

        payload_user = {"user_id": user.user_id, "tenant_id": user.tenant_id, "roles": user.roles}
        result = await self.mcp.execute(tool_to_call, args, payload_user, trace_id)
        text = ""
        if isinstance(result, dict) and result.get("status") == "ok":
            res_body = result.get("result") or {}
            if isinstance(res_body, dict):
                if "chunks" in res_body:
                    text = " ".join(chunk.get("text", "") for chunk in res_body.get("chunks", []) if chunk.get("text"))
                else:
                    text = res_body.get("text", "")
        tokens_used = len(text) // 4 if text else 0
        return result, tokens_used
