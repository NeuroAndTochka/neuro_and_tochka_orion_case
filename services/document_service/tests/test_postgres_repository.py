from __future__ import annotations

import json
import os
import shutil
import subprocess
from uuid import uuid4

import pytest
import pytest_asyncio
from docker.errors import DockerException
from testcontainers.postgres import PostgresContainer

from document_service.core.repository import DocumentRepository
from document_service.db import create_engine, create_session_factory, init_db
from document_service.models import Base
from document_service.schemas import (
    DocumentCreateRequest,
    SectionUpsertItem,
    StatusUpdateRequest,
)


POSTGRES_IMAGE = os.getenv("DOC_TEST_POSTGRES_IMAGE", "postgres:16")


def _ensure_docker_host_from_context() -> None:
    if os.getenv("DOCKER_HOST"):
        return
    docker_bin = shutil.which("docker")
    if not docker_bin:
        return
    try:
        raw = subprocess.check_output(
            [docker_bin, "context", "inspect"],
            stderr=subprocess.DEVNULL,
        )
        contexts = json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return
    if not contexts:
        return
    host = contexts[0].get("Endpoints", {}).get("docker", {}).get("Host")
    if host:
        os.environ["DOCKER_HOST"] = host


@pytest.fixture(scope="session")
def postgres_container():
    if os.getenv("DOC_TEST_POSTGRES_DSN"):
        # Вручную задан DSN — используем внешнюю БД без контейнера.
        yield None
        return
    _ensure_docker_host_from_context()
    container: PostgresContainer | None = None
    try:
        container = PostgresContainer(POSTGRES_IMAGE)
        container.start()
    except DockerException as exc:
        pytest.skip(f"Docker is required for Postgres testcontainers: {exc}")
    try:
        assert container is not None
        yield container
    finally:
        if container is not None:
            container.stop()


@pytest.fixture(scope="session")
def postgres_dsn(postgres_container: PostgresContainer | None) -> str:
    env_dsn = os.getenv("DOC_TEST_POSTGRES_DSN")
    if env_dsn:
        return env_dsn
    assert postgres_container is not None
    sync_dsn = postgres_container.get_connection_url()
    sync_dsn = sync_dsn.replace("0.0.0.0", "127.0.0.1")
    if "postgresql+psycopg2" in sync_dsn:
        return sync_dsn.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return sync_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest_asyncio.fixture
async def postgres_engine(postgres_dsn: str):
    engine = create_engine(postgres_dsn)
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def clean_database(postgres_engine):
    async with postgres_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


def _new_doc_payload(tenant: str = "tenant_pg") -> DocumentCreateRequest:
    doc_id = f"doc_{uuid4().hex[:8]}"
    return DocumentCreateRequest(
        doc_id=doc_id,
        tenant_id=tenant,
        name=f"Postgres Spec {doc_id}",
        product="Observer",
        version="1.0",
        status="uploaded",
        storage_uri=f"s3://bucket/{tenant}/{doc_id}/original.pdf",
        pages=12,
        tags=["postgres", "integration"],
    )


@pytest.mark.asyncio
async def test_repository_crud_cycle(postgres_engine, clean_database):  # noqa: ARG001
    session_factory = create_session_factory(postgres_engine)
    async with session_factory() as session:
        repo = DocumentRepository(session)
        payload = _new_doc_payload()

        detail = await repo.create_or_update_document(payload)
        assert detail.doc_id == payload.doc_id
        assert detail.storage_uri == payload.storage_uri

        total, items = await repo.list_documents(payload.tenant_id, {}, limit=10, offset=0)
        assert total == 1
        assert items[0].doc_id == payload.doc_id

        sections = [
            SectionUpsertItem(
                section_id="sec_intro",
                title="Intro",
                page_start=1,
                page_end=2,
                chunk_ids=["chunk-pg-1"],
                summary="Intro summary",
            )
        ]
        updated = await repo.upsert_sections(payload.doc_id, payload.tenant_id, sections)
        assert updated
        assert updated.sections[0].section_id == "sec_intro"

        tenant_id = await repo.update_status(
            StatusUpdateRequest(
                doc_id=payload.doc_id,
                status="indexed",
                storage_uri=payload.storage_uri,
                pages=15,
            )
        )
        assert tenant_id == payload.tenant_id

        final = await repo.get_document(payload.doc_id, payload.tenant_id)
        assert final
        assert final.status == "indexed"
        assert final.pages == 15
