import pathlib
import sys

import httpx
import pytest
from fastapi import FastAPI

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "mcp_tools_proxy"))

from llm_service.config import Settings
from llm_service.core.orchestrator import LLMOrchestrator
from llm_service.schemas import ContextChunk, GenerateRequest, Message
from mcp_tools_proxy.main import app as mcp_app


@pytest.mark.anyio
async def test_llm_service_with_real_mcp_proxy() -> None:
    runtime_app = FastAPI()
    runtime_app.state.tool_invoked = False

    @runtime_app.post("/v1/chat/completions")
    async def completions(payload: dict):  # type: ignore[override]
        if runtime_app.state.tool_invoked:
            return {
                "choices": [
                    {
                        "message": {"content": "Final answer using MCP snippet"},
                    }
                ],
                "usage": {"prompt_tokens": 200, "completion_tokens": 80},
            }
        runtime_app.state.tool_invoked = True
        return {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "read_doc_section",
                                    "arguments": {"doc_id": "doc_1", "section_id": "sec_intro"},
                                },
                            }
                        ]
                    }
                }
            ],
            "usage": {"prompt_tokens": 150, "completion_tokens": 60},
        }

    aggregator = FastAPI()
    aggregator.mount("/mcp", mcp_app)
    aggregator.mount("/runtime", runtime_app)

    transport = httpx.ASGITransport(app=aggregator)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings = Settings(
            mock_mode=False,
            llm_runtime_url="http://testserver/runtime/v1/chat/completions",
            mcp_proxy_url="http://testserver/mcp/internal/mcp/execute",
            default_model="test-model",
            max_tool_steps=2,
            enable_json_mode=False,
        )
        orchestrator = LLMOrchestrator(settings, client)
        request = GenerateRequest(
            system_prompt="You are Visior",
            messages=[Message(role="user", content="Need tool call")],
            context_chunks=[ContextChunk(doc_id="doc_1", section_id="sec_intro", text="LDAP context", page_start=1, page_end=2)],
        )
        response = await orchestrator.generate(request)
        assert response.meta["tool_steps"] == 1
        assert response.tools_called
        assert "MCP snippet" in response.answer
