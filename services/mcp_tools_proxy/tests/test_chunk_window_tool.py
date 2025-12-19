import httpx
import pytest

from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.core.executor import ToolRegistry
from mcp_tools_proxy.clients.retrieval import RetrievalClient
from mcp_tools_proxy.main import app as mcp_app
from retrieval_service.main import app as retrieval_app


@pytest.mark.anyio
async def test_read_chunk_window_uses_retrieval_service() -> None:
    retrieval_transport = httpx.ASGITransport(app=retrieval_app)
    retrieval_url = "http://retrieval.local/internal/retrieval/chunks/window"
    registry = ToolRegistry(
        Settings(
            mock_mode=True,
            retrieval_window_url=retrieval_url,
        ),
        retrieval_client=RetrievalClient(retrieval_url, transport=retrieval_transport),
    )
    mcp_app.state.tool_registry = registry

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mcp_app), base_url="http://mcp.local") as client:
        resp = await client.post(
            "/internal/mcp/execute",
            json={
                "tool_name": "read_chunk_window",
                "arguments": {"doc_id": "doc_1", "anchor_chunk_id": "chunk_1", "window_before": 0, "window_after": 0},
                "user": {"user_id": "u", "tenant_id": "tenant_1"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["result"]["chunks"]
        assert data["result"]["chunks"][0]["chunk_id"] == "chunk_1"


@pytest.mark.anyio
async def test_read_chunk_window_limit_error_is_structured() -> None:
    registry = ToolRegistry(Settings(mock_mode=False, max_window_radius=2))
    req = {
        "tool_name": "read_chunk_window",
        "arguments": {"doc_id": "doc_1", "anchor_chunk_id": "chunk_1", "window_before": 3, "window_after": 3},
        "user": {"user_id": "u", "tenant_id": "tenant_1"},
        "trace_id": "trace-limit",
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mcp_app), base_url="http://mcp.local") as client:
        mcp_app.state.tool_registry = registry
        resp = await client.post("/internal/mcp/execute", json=req)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "WINDOW_TOO_LARGE"
    assert "radius 3" in data["error"]["message"]


@pytest.mark.anyio
async def test_read_chunk_window_respects_radius_not_total() -> None:
    retrieval_transport = httpx.ASGITransport(app=retrieval_app)
    retrieval_url = "http://retrieval.local/internal/retrieval/chunks/window"
    registry = ToolRegistry(
        Settings(mock_mode=True, retrieval_window_url=retrieval_url, max_window_radius=2),
        retrieval_client=RetrievalClient(retrieval_url, transport=retrieval_transport),
    )
    mcp_app.state.tool_registry = registry

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=mcp_app), base_url="http://mcp.local") as client:
        resp = await client.post(
            "/internal/mcp/execute",
            json={
                "tool_name": "read_chunk_window",
                "arguments": {"doc_id": "doc_1", "anchor_chunk_id": "chunk_1", "window_before": 2, "window_after": 2},
                "user": {"user_id": "u", "tenant_id": "tenant_1"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["result"]["window_before"] == 2
        assert data["result"]["window_after"] == 2
