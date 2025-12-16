import pytest
from fastapi import HTTPException, status

from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.core.executor import ToolRegistry
from mcp_tools_proxy.schemas import MCPExecuteRequest, MCPUser


class FailingRetrievalClient:
    async def fetch_chunk_window(
        self, *, tenant_id: str, doc_id: str, anchor_chunk_id: str, window_before: int, window_after: int, trace_id: str | None = None
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "retrieval_error", "message": {"detail": "Expected include item to be one of ... got ids"}},
        )


@pytest.mark.anyio
async def test_mcp_error_message_is_string():
    settings = Settings(mock_mode=False, retrieval_window_url="http://example.com")
    registry = ToolRegistry(settings, retrieval_client=FailingRetrievalClient())
    req = MCPExecuteRequest(
        tool_name="read_chunk_window",
        arguments={"doc_id": "doc_1", "anchor_chunk_id": "chunk_1", "window_before": 0, "window_after": 0},
        user=MCPUser(user_id="u", tenant_id="tenant_1"),
    )
    resp = await registry.execute(req)
    assert resp.status == "error"
    assert isinstance(resp.error.message, str)
    assert "include" in resp.error.message
