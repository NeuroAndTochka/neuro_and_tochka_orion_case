from fastapi.testclient import TestClient

from ai_orchestrator.main import app


def payload(query: str = "Привет") -> dict:
    return {
        "conversation_id": "conv_1",
        "user": {"user_id": "u", "tenant_id": "tenant_1", "roles": ["support"]},
        "query": query,
        "channel": "web",
        "trace_id": "trace-123",
    }


def test_orchestrator_returns_answer():
    with TestClient(app) as client:
        resp = client.post("/internal/orchestrator/respond", json=payload())
        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"].startswith("Mock answer")
        assert data["telemetry"]["trace_id"] == "trace-123"
