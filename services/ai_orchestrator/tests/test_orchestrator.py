import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from ai_orchestrator.config import Settings
from ai_orchestrator.clients.runtime import RuntimeResult
from ai_orchestrator.core.orchestrator import Orchestrator, ProgressiveWindowState
from ai_orchestrator.schemas import OrchestratorRequest, UserContext


@pytest.mark.anyio
async def test_progressive_window_respects_radius_cap():
    settings = Settings(mock_mode=True, window_radius=2)
    async with httpx.AsyncClient() as client:
        orchestrator = Orchestrator(settings, client)

        calls = []

        async def fake_execute(tool_name, arguments, user, trace_id):
            calls.append((tool_name, arguments))
            return {"status": "ok", "result": {"chunks": [{"text": "hello"}]}}

        orchestrator.mcp.execute = fake_execute  # type: ignore[assignment]

        window_state = ProgressiveWindowState(
            initial=min(1, settings.window_radius), step=1, max_window=settings.window_radius
        )
        section_chunk_map = {"sec_intro": "chunk_1"}
        await orchestrator._execute_tool(
            "read_chunk_window", {"doc_id": "doc_1", "section_id": "sec_intro"}, section_chunk_map, window_state, UserContext(user_id="u", tenant_id="t"), "trace"
        )
        await orchestrator._execute_tool(
            "read_chunk_window", {"doc_id": "doc_1", "section_id": "sec_intro"}, section_chunk_map, window_state, UserContext(user_id="u", tenant_id="t"), "trace"
        )
        await orchestrator._execute_tool(
            "read_chunk_window", {"doc_id": "doc_1", "section_id": "sec_intro"}, section_chunk_map, window_state, UserContext(user_id="u", tenant_id="t"), "trace"
        )

        assert [c[1]["window_before"] for c in calls] == [1, 2, 2]
        assert all(c[1]["window_after"] <= settings.window_radius for c in calls)


@pytest.mark.anyio
async def test_orchestrator_clamps_llm_requested_window_to_radius():
    settings = Settings(mock_mode=True, window_radius=1)
    async with httpx.AsyncClient() as client:
        orchestrator = Orchestrator(settings, client)

        calls = []

        async def fake_execute(tool_name, arguments, user, trace_id):
            calls.append((tool_name, arguments))
            return {"status": "ok", "result": {"chunks": [{"text": "hi"}]}}

        orchestrator.mcp.execute = fake_execute  # type: ignore[assignment]

        window_state = ProgressiveWindowState(initial=min(1, settings.window_radius), step=1, max_window=settings.window_radius)
        section_chunk_map = {"sec_intro": "chunk_1"}
        await orchestrator._execute_tool(
            "read_chunk_window",
            {"doc_id": "doc_1", "section_id": "sec_intro", "window_before": 5, "window_after": 3},
            section_chunk_map,
            window_state,
            UserContext(user_id="u", tenant_id="t"),
            "trace",
        )

        assert calls
        assert calls[0][1]["window_before"] == settings.window_radius
        assert calls[0][1]["window_after"] == settings.window_radius


@pytest.mark.anyio
async def test_orchestrator_runs_with_mock_runtime_and_mcp():
    settings = Settings(mock_mode=True)
    async with httpx.AsyncClient() as client:
        orchestrator = Orchestrator(settings, client)
        req = OrchestratorRequest(query="Tell me about LDAP", tenant_id="tenant_1", user_id="user_1")
        resp = await orchestrator.respond(req)
        assert resp.answer
        assert resp.tools  # tool was called
        assert resp.sources


@pytest.mark.anyio
async def test_first_prompt_uses_summaries_only():
    settings = Settings(mock_mode=False)
    async with httpx.AsyncClient() as client:
        orchestrator = Orchestrator(settings, client)
        orchestrator.retrieval.search = AsyncMock(  # type: ignore[assignment]
            return_value=(
                [{"doc_id": "doc_1", "section_id": "sec_intro", "summary": "Short summary", "text": "RAW_SECTION_TEXT"}],
                None,
            )
        )
        captured = {}

        async def fake_chat(payload):
            captured["payload"] = payload
            return RuntimeResult(type="message", content="ok", tool_name=None, tool_arguments=None, usage={"prompt_tokens": 0, "completion_tokens": 0})

        orchestrator.runtime.chat_completion = fake_chat  # type: ignore[assignment]
        orchestrator.mcp.execute = AsyncMock(return_value={"status": "ok", "result": {"text": "full section"}})  # type: ignore[assignment]

        req = OrchestratorRequest(query="Need info", user_id="u", tenant_id="t")
        await orchestrator.respond(req)
        ctx_msg = next(m for m in captured["payload"]["messages"] if "Retrieved sections" in m["content"])
        assert "RAW_SECTION_TEXT" not in ctx_msg["content"]
        assert "Short summary" in ctx_msg["content"]


@pytest.mark.anyio
async def test_orchestrator_uses_mcp_when_no_chunks():
    settings = Settings(mock_mode=False, max_tool_steps=1)
    async with httpx.AsyncClient() as client:
        orchestrator = Orchestrator(settings, client)
        orchestrator.retrieval.search = AsyncMock(  # type: ignore[assignment]
            return_value=([{"doc_id": "doc_1", "section_id": "sec_intro", "summary": "Short summary"}], None)
        )
        runtime_calls = []

        async def fake_chat(payload):
            runtime_calls.append(payload)
            if len(runtime_calls) == 1:
                return RuntimeResult(
                    type="tool_call",
                    content=None,
                    tool_name="read_chunk_window",
                    tool_arguments={"doc_id": "doc_1", "section_id": "sec_intro"},
                    usage={"prompt_tokens": 0, "completion_tokens": 0},
                )
            return RuntimeResult(type="message", content="done", tool_name=None, tool_arguments=None, usage={"prompt_tokens": 0, "completion_tokens": 0})

        orchestrator.runtime.chat_completion = fake_chat  # type: ignore[assignment]
        mcp_calls = []

        async def fake_execute(tool_name, args, user, trace_id):
            mcp_calls.append((tool_name, args))
            return {"status": "ok", "result": {"text": "full section"}}

        orchestrator.mcp.execute = fake_execute  # type: ignore[assignment]

        await orchestrator.respond(OrchestratorRequest(query="Tell me", user_id="u", tenant_id="t"))
        assert mcp_calls and mcp_calls[0][0] == "read_doc_section"
        # second runtime call should include tool result message only after MCP execution
        assert any(
            str(msg.get("content", "")).startswith("TOOL_RESULT")
            for msg in runtime_calls[-1]["messages"]
            if isinstance(msg, dict) and msg.get("role") == "assistant"
        )


@pytest.mark.anyio
async def test_tool_schema_advertises_radius_limits():
    settings = Settings(mock_mode=True, window_radius=4)
    async with httpx.AsyncClient() as client:
        orchestrator = Orchestrator(settings, client)
        tools = orchestrator._tool_schemas()
    chunk_tool = next(t for t in tools if t["function"]["name"] == "read_chunk_window")
    props = chunk_tool["function"]["parameters"]["properties"]
    assert props["window_before"]["maximum"] == settings.window_radius
    assert props["window_after"]["maximum"] == settings.window_radius
    assert props["radius"]["maximum"] == settings.window_radius
