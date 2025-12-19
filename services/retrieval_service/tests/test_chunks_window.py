from fastapi.testclient import TestClient

from retrieval_service.main import app
from retrieval_service.config import get_settings


class DummyCollection:
    def __init__(self) -> None:
        self.last_include = None

    def get(self, where, include=None, limit=None):
        self.last_include = include
        return {
            "ids": ["doc:chunk_1"],
            "metadatas": [
                {"chunk_id": "doc:chunk_1", "text": "hello", "chunk_index": 0, "page": 1},
            ],
        }


class DummyIndex:
    def __init__(self) -> None:
        self.collection = DummyCollection()


def test_chunk_window_does_not_request_ids(monkeypatch):
    old_index = getattr(app.state, "index", None)
    old_settings = getattr(app.state, "settings", None)
    app.state.index = DummyIndex()
    app.state.settings = old_settings or get_settings()
    client = TestClient(app)

    resp = client.post(
        "/internal/retrieval/chunks/window",
        json={"tenant_id": "tenant_x", "doc_id": "doc", "anchor_chunk_id": "doc:chunk_1", "window_before": 0, "window_after": 0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["chunks"][0]["chunk_id"] == "doc:chunk_1"
    # Ensure Chroma .get was called without forbidden 'ids' include
    assert app.state.index.collection.last_include == ["metadatas"]
    # restore
    app.state.index = old_index
    app.state.settings = old_settings
