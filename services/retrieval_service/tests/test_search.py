from fastapi.testclient import TestClient

from retrieval_service.main import app


def test_search_returns_hits():
    with TestClient(app) as client:
        resp = client.post(
            "/internal/retrieval/search",
            json={"query": "ldap", "tenant_id": "tenant_1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hits"]
        assert data["hits"][0]["doc_id"] == "doc_1"
        assert "steps" in data


def test_search_respects_max_results_cap():
    with TestClient(app) as client:
        resp = client.post(
            "/internal/retrieval/search",
            json={"query": "s", "tenant_id": "tenant_1", "max_results": 1},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["hits"]) == 1


def test_search_filters_doc_ids():
    with TestClient(app) as client:
        resp = client.post(
            "/internal/retrieval/search",
            json={"query": "sso", "tenant_id": "tenant_1", "doc_ids": ["doc_1"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        # sso текст есть только в doc_2, поэтому при фильтре doc_1 — пусто
        assert data["hits"] == []


def test_chunk_window_missing_fields():
    with TestClient(app) as client:
        resp = client.post("/internal/retrieval/chunks/window", json={"tenant_id": "t", "doc_id": "d"})
        assert resp.status_code == 400
