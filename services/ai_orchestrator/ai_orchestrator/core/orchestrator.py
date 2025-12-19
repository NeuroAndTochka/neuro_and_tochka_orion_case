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
        self.max_window = max(0, max_window)
        self.initial = max(0, min(initial, self.max_window))
        self.step = max(1, step) if self.max_window > 0 else 1
        self.window_by_section: Dict[str, int] = {}
        self.tokens_used: int = 0

    def next_window(self, section_id: str) -> int:
        current = self.window_by_section.get(section_id, self.initial)
        clamped_current = min(current, self.max_window)
        self.window_by_section[section_id] = min(self.max_window, clamped_current + self.step)
        return clamped_current

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
        retrieval_payload = {
            "query": request.query,
            "tenant_id": user_context.tenant_id,
            "filters": request.filters,
            "doc_ids": request.doc_ids,
            "section_ids": request.section_ids,
            "max_results": request.max_results,
            "trace_id": trace_id,
        }
        for field in [
            "docs_top_k",
            "sections_top_k_per_doc",
            "max_total_sections",
            "rerank_score_threshold",
            "enable_section_cosine",
            "enable_rerank",
        ]:
            value = getattr(request, field, None)
            if value is not None:
                retrieval_payload[field] = value
        if request.rerank_enabled is not None and "enable_rerank" not in retrieval_payload:
            retrieval_payload["enable_rerank"] = request.rerank_enabled
        retrieval_hits, retrieval_steps = await self.retrieval.search(retrieval_payload)
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
        self._logger.info(
            "orchestrator_retrieval_hits",
            trace_id=trace_id,
            tenant_id=user_context.tenant_id,
            total_hits=len(retrieval_hits),
            hits=[
                {
                    "doc_id": h.get("doc_id"),
                    "section_id": h.get("section_id"),
                    "chunk_id": h.get("chunk_id"),
                    "score": h.get("score"),
                }
                for h in retrieval_hits
            ],
        )

        sections = self._select_sections(retrieval_hits)
        context = build_context(sections, self.settings.prompt_token_budget)
        section_chunk_map = self._build_section_chunk_index(sections)
        summaries_len = sum(len(item.get("summary") or "") for item in context)
        self._logger.info(
            "orchestrator_context_prepared",
            trace_id=trace_id,
            tenant_id=user_context.tenant_id,
            sections=len(context),
            doc_ids=sorted({c.get("doc_id") for c in context if c.get("doc_id")}),
            section_ids=[c.get("section_id") for c in context if c.get("section_id")],
            summary_chars=summaries_len,
            chunk_anchor_map=len(section_chunk_map),
        )
        messages = self._build_messages(request.query, context)
        tools = self._tool_schemas()
        usage = {"prompt": 0, "completion": 0}
        window_state = ProgressiveWindowState(
            initial=min(1, self.settings.window_radius) if self.settings.window_radius > 0 else 0,
            step=1,
            max_window=self.settings.window_radius,
        )
        tool_traces: List[ToolCallTrace] = []

        for step in range(self.settings.max_tool_steps + 1):
            payload = {
                "model": "mock-model" if self.settings.mock_mode else self.settings.default_model,
                "messages": messages,
                "tools": tools,
                "context": context,
            }
            tool_results = [
                m for m in messages if isinstance(m, dict) and m.get("role") == "assistant" and str(m.get("content", "")).startswith("TOOL_RESULT")
            ]
            self._logger.info(
                "orchestrator_llm_request",
                trace_id=trace_id,
                tenant_id=user_context.tenant_id,
                model=payload["model"],
                empty_context=not bool(context),
                context_sections=len(context),
                tool_results=len(tool_results),
                tool_result_chars=sum(len(str(m.get("content", ""))) for m in tool_results),
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
            self._logger.info(
                "orchestrator_tool_call_raw",
                trace_id=trace_id,
                tenant_id=user_context.tenant_id,
                tool=tool_name,
                raw_arguments=arguments,
                max_window_radius=self.settings.window_radius,
            )
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
            """You are Visior, a tool-using RAG assistant.

            You start with section summaries/metadata only. You may call tools to fetch raw text, but you must avoid tool loops.

            Core rules:
            - Never reveal chain-of-thought. Output only the final answer.
            - Answer primarily from the retrieved summaries when they are sufficient.
            - Tool calls are allowed ONLY to verify or extract missing critical details (commands, file paths, exact wording, constraints).
            - After at most 3 tool calls, you MUST produce a final answer using what you have.
            - NEVER call the same tool with the same (doc_id, section_id, anchor_chunk_id, window_before, window_after) more than once.
            - Prefer minimal text retrieval: start with a small window; expand only once if needed.

            Window policy (text retrieval):
            - First attempt: window_before=1, window_after=1 (3 chunks total).
            - Second attempt (only if necessary): window_before=2, window_after=2 (5 chunks total).
            - Do not expand beyond 5 chunks total.

            If information is still missing after 3 tool calls, say exactly what is missing and how the user can provide it.

            Citations:
            - Every concrete recommendation must be cited as [doc_id/section_id].

            """
        )
        developer_msg = (
            """Tool policy (strict):
            1) Decide if a tool call is truly necessary. If summaries already answer the question, do NOT call tools.
            2) If needed, call read_doc_section ONCE for the single most relevant section.
            3) If still missing a critical detail, call read_doc_section at most one more time (either expand the window once or pick the second-best section).
            4) After 0–2 tool calls, finalize the user-facing answer.
            5) Never repeat the same read_doc_section request for the same section.
            6) Keep the final answer short and operational: steps + commands + citations.

            """
        )
        return [
            {"role": "system", "content": system_msg},
            {"role": "system", "content": developer_msg},
            {"role": "system", "content": f"Retrieved sections (summaries only): {context_block}"},
            {"role": "user", "content": query},
        ]

    def _tool_schemas(self) -> List[Dict[str, Any]]:
        radius = max(0, self.settings.window_radius)
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
                            "window_before": {"type": "integer", "minimum": 0, "maximum": radius},
                            "window_after": {"type": "integer", "minimum": 0, "maximum": radius},
                            "radius": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": radius,
                                "description": "Optional alias to request the same window before/after the anchor. Total chunks = 2R+1.",
                            },
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
            anchor = sec.get("anchor_chunk_id")
            chunk_ids = sec.get("chunk_ids") or []
            if isinstance(chunk_ids, list) and not anchor and chunk_ids:
                anchor = chunk_ids[0]
            if not anchor:
                anchor = sec.get("chunk_id")
            if sec_id and anchor:
                mapping[sec_id] = anchor
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
        effective_radius = max(0, self.settings.window_radius)
        window = window_state.next_window(section_id) if section_id else min(1, effective_radius)
        raw_arguments = dict(arguments)

        if raw_arguments.get("radius") is not None:
            radius_arg = int(raw_arguments.get("radius") or 0)
            window_before = radius_arg
            window_after = radius_arg
        else:
            window_before = int(raw_arguments.get("window_before", window))
            window_after = int(raw_arguments.get("window_after", window))

        window_before = max(0, min(window_before, effective_radius))
        window_after = max(0, min(window_after, effective_radius))

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

        self._logger.info(
            "orchestrator_tool_call",
            trace_id=trace_id,
            tenant_id=user.tenant_id,
            tool=tool_to_call,
            doc_id=doc_id,
            section_id=section_id,
            anchor_chunk_id=anchor_chunk_id,
            raw_arguments=raw_arguments,
            window_before=window_before,
            window_after=window_after,
            requested_chunks=window_before + window_after + 1 if anchor_chunk_id else None,
            effective_window_radius=effective_radius,
        )
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
