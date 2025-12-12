from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from fastapi.testclient import TestClient

TEST_DIR = Path(__file__).parent
DB_PATH = TEST_DIR / "observer_test.db"
ROOT = TEST_DIR.parents[2]

sys.path.append(str(ROOT / "services" / "ml_observer"))

os.environ.setdefault("OBS_DB_DSN", f"sqlite+aiosqlite:///{DB_PATH}")
os.environ.setdefault("OBS_MOCK_MODE", "true")

from ml_observer.main import app  # noqa: E402


def tenant_headers(tenant: str = "observer_tenant") -> dict[str, str]:
    return {"X-Tenant-ID": tenant}


def setup_module() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    storage = ROOT / "services" / "ml_observer" / ".observer_storage"
    if storage.exists():
        shutil.rmtree(storage)


def teardown_module() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_experiment_flow():
    with TestClient(app) as client:
        resp = client.post(
            "/internal/observer/experiments",
            json={"name": "Test Experiment", "description": "dry run", "params": {"top_k": 5}},
            headers=tenant_headers(),
        )
        assert resp.status_code == 201, resp.text
        exp = resp.json()
        exp_id = exp["experiment_id"]

        resp = client.get(f"/internal/observer/experiments/{exp_id}", headers=tenant_headers())
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Experiment"

        resp = client.post(
            "/internal/observer/documents/upload",
            json={"doc_id": "doc_demo", "name": "Demo Doc", "experiment_id": exp_id},
            headers=tenant_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "queued"

        resp = client.get("/internal/observer/documents/doc_demo", headers=tenant_headers())
        assert resp.status_code == 200
        assert resp.json()["doc_id"] == "doc_demo"

        resp = client.post(
            "/internal/observer/retrieval/run",
            json={"queries": ["ldap guide"], "top_k": 3, "experiment_id": exp_id},
            headers=tenant_headers(),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["hits"]
        assert body["status"] == "completed"

        resp = client.post(
            "/internal/observer/llm/dry-run",
            json={"prompt": "Explain LDAP", "context": ["LDAP is ..."], "experiment_id": exp_id},
            headers=tenant_headers(),
        )
        assert resp.status_code == 201
        assert resp.json()["answer"]

        resp = client.get(f"/internal/observer/experiments/{exp_id}", headers=tenant_headers())
        assert resp.status_code == 200
        detail = resp.json()
        assert len(detail["runs"]) >= 2
