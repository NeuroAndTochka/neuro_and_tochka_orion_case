from fastapi.testclient import TestClient

from ingestion_service.main import app


def tenant_headers():
    return {"X-Tenant-ID": "tenant_1"}


def test_enqueue_document(tmp_path, monkeypatch):
    with TestClient(app) as client:
        files = {"file": ("test.txt", b"hello", "text/plain")}
        resp = client.post("/internal/ingestion/enqueue", files=files, headers=tenant_headers())
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "queued"


def test_update_status():
    with TestClient(app) as client:
        files = {"file": ("test.txt", b"hello", "text/plain")}
        enqueue = client.post("/internal/ingestion/enqueue", files=files, headers=tenant_headers())
        job_id = enqueue.json()["job_id"]
        resp = client.post(
            "/internal/ingestion/status",
            json={"job_id": job_id, "doc_id": "irrelevant", "status": "processing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"
