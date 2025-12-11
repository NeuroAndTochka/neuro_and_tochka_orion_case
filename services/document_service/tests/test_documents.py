from fastapi.testclient import TestClient

from document_service.main import app


def tenant_headers():
    return {"X-Tenant-ID": "tenant_1"}


def test_list_documents():
    with TestClient(app) as client:
        resp = client.get("/internal/documents", headers=tenant_headers())
        assert resp.status_code == 200
        assert resp.json()


def test_get_document_detail():
    with TestClient(app) as client:
        resp = client.get("/internal/documents/doc_1", headers=tenant_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["doc_id"] == "doc_1"
        assert body["sections"]


def test_update_status():
    with TestClient(app) as client:
        resp = client.post(
            "/internal/documents/status",
            json={"doc_id": "doc_1", "status": "processing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"


def test_get_section():
    with TestClient(app) as client:
        resp = client.get("/internal/documents/doc_1/sections/sec_intro", headers=tenant_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["section_id"] == "sec_intro"


def test_tenant_isolation():
    headers = {"X-Tenant-ID": "another"}
    with TestClient(app) as client:
        resp = client.get("/internal/documents/doc_1", headers=headers)
        assert resp.status_code == 404
