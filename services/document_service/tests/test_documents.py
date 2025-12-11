from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

TEST_DIR = Path(__file__).parent
DB_PATH = TEST_DIR / "document_test.db"
LOCAL_STORAGE = TEST_DIR / "local_storage"
ROOT = TEST_DIR.parents[2]

sys.path.append(str(ROOT / "services" / "document_service"))

os.environ.setdefault("DOC_DB_DSN", f"sqlite+aiosqlite:///{DB_PATH}")
os.environ.setdefault("DOC_LOCAL_STORAGE_PATH", str(LOCAL_STORAGE))
os.environ.setdefault("DOC_MOCK_MODE", "true")

from document_service.main import app  # noqa: E402


def tenant_headers(tenant: str = "tenant_1") -> dict[str, str]:
    return {"X-Tenant-ID": tenant}


def setup_module() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    if LOCAL_STORAGE.exists():
        shutil.rmtree(LOCAL_STORAGE)


def teardown_module() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    if LOCAL_STORAGE.exists():
        shutil.rmtree(LOCAL_STORAGE)


def _create_document(client: TestClient, tenant: str = "tenant_1", storage_uri: str | None = None) -> str:
    doc_id = f"doc_{uuid4().hex[:8]}"
    payload = {
        "doc_id": doc_id,
        "tenant_id": tenant,
        "name": f"Spec {doc_id}",
        "product": "Orion",
        "version": "1.0",
        "status": "uploaded",
        "storage_uri": storage_uri,
        "pages": 10,
        "tags": ["ldap", "admin"],
    }
    resp = client.post("/internal/documents", json=payload)
    assert resp.status_code == 201, resp.text
    return doc_id


def _upsert_sections(client: TestClient, doc_id: str, tenant: str = "tenant_1") -> None:
    resp = client.post(
        f"/internal/documents/{doc_id}/sections",
        headers=tenant_headers(tenant),
        json={
            "sections": [
                {
                    "section_id": "sec_intro",
                    "title": "Intro",
                    "page_start": 1,
                    "page_end": 2,
                    "chunk_ids": ["chunk_1"],
                }
            ]
        },
    )
    assert resp.status_code == 200


def test_create_and_list_documents():
    with TestClient(app) as client:
        doc_id = _create_document(client)
        resp = client.get("/internal/documents", headers=tenant_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        assert any(item["doc_id"] == doc_id for item in body["items"])


def test_get_document_detail_and_sections():
    with TestClient(app) as client:
        doc_id = _create_document(client)
        _upsert_sections(client, doc_id)
        resp = client.get(f"/internal/documents/{doc_id}", headers=tenant_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["doc_id"] == doc_id
        assert body["sections"]


def test_get_specific_section():
    with TestClient(app) as client:
        doc_id = _create_document(client)
        _upsert_sections(client, doc_id)
        resp = client.get(
            f"/internal/documents/{doc_id}/sections/sec_intro",
            headers=tenant_headers(),
        )
        assert resp.status_code == 200
        assert resp.json()["section_id"] == "sec_intro"


def test_update_status_changes_state():
    with TestClient(app) as client:
        doc_id = _create_document(client)
        resp = client.post(
            "/internal/documents/status",
            json={"doc_id": doc_id, "status": "processing"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "processing"


def test_download_url_local_scheme(tmp_path: Path):
    local_key = f"tenant_1/{uuid4().hex}/original.pdf"
    storage_uri = f"local://{local_key}"
    with TestClient(app) as client:
        doc_id = _create_document(client, storage_uri=storage_uri)
        target = LOCAL_STORAGE / local_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"hello")
        resp = client.get(f"/internal/documents/{doc_id}/download-url", headers=tenant_headers())
        assert resp.status_code == 200
        url = resp.json()["url"]
        assert url.startswith("file:")


def test_tenant_isolation_rejected():
    with TestClient(app) as client:
        doc_id = _create_document(client, tenant="tenant_1")
        resp = client.get(f"/internal/documents/{doc_id}", headers=tenant_headers("another"))
        assert resp.status_code == 404
