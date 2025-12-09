from fastapi.testclient import TestClient

from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.core.executor import ToolRegistry
from mcp_tools_proxy.main import app


def _apply_registry(**overrides) -> None:
    settings = Settings(**overrides)
    app.state.tool_registry = ToolRegistry(settings)


def test_read_doc_section_success() -> None:
    _apply_registry()
    with TestClient(app) as client:
        resp = client.post(
            "/internal/mcp/execute",
            json={
                "tool_name": "read_doc_section",
                "arguments": {"doc_id": "doc_1", "section_id": "sec_intro"},
                "user": {"user_id": "u", "tenant_id": "tenant_1"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "text" in body["result"]


def test_denied_for_wrong_tenant() -> None:
    _apply_registry()
    with TestClient(app) as client:
        resp = client.post(
            "/internal/mcp/execute",
            json={
                "tool_name": "read_doc_section",
                "arguments": {"doc_id": "doc_1", "section_id": "sec_intro"},
                "user": {"user_id": "u", "tenant_id": "another"},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["error"]["code"] == "ACCESS_DENIED"


def test_rate_limit_triggered() -> None:
    _apply_registry(rate_limit_calls=1, rate_limit_tokens=50)
    payload = {
        "tool_name": "read_doc_section",
        "arguments": {"doc_id": "doc_1", "section_id": "sec_intro"},
        "user": {"user_id": "u", "tenant_id": "tenant_1"},
    }
    with TestClient(app) as client:
        first = client.post("/internal/mcp/execute", json=payload)
        assert first.status_code == 200
        second = client.post("/internal/mcp/execute", json=payload)
        assert second.status_code == 200
        assert second.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
