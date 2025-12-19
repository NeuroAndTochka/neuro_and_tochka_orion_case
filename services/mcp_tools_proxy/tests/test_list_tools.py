from fastapi.testclient import TestClient

from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.core.executor import ToolRegistry
from mcp_tools_proxy.main import app


def test_list_tools_returns_tool_names() -> None:
    app.state.tool_registry = ToolRegistry(Settings())
    with TestClient(app) as client:
        resp = client.post(
            "/internal/mcp/execute",
            json={
                "tool_name": "list_available_tools",
                "arguments": {},
                "user": {"user_id": "u", "tenant_id": "tenant_1"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "read_doc_section" in data["result"]["tools"]
        assert "read_chunk_window" in data["result"]["tools"]
