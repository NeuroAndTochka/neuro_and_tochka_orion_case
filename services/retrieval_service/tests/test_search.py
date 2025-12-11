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
