from fastapi.testclient import TestClient

from retrieval_service.main import app
from retrieval_service.core.index import ChromaIndex, chromadb
from retrieval_service.core.embedding import EmbeddingClient
from retrieval_service.config import Settings
from retrieval_service.schemas import RetrievalFilters, RetrievalQuery


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
        assert "text" not in data["hits"][0]
        assert data["hits"][0]["summary"]
        assert data["hits"][0].get("anchor_chunk_id") == data["hits"][0].get("chunk_id")
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


def test_chroma_search_with_metadata_filters(tmp_path):
    if chromadb is None:
        return
    settings = Settings(
        mock_mode=False,
        vector_backend="chroma",
        chroma_path=str(tmp_path),
        embedding_api_base=None,
        embedding_api_key=None,
        min_docs=0,
    )
    embedding = EmbeddingClient(settings)
    client = chromadb.PersistentClient(path=str(tmp_path))
    index = ChromaIndex(
        client=client,
        collection_name="ingestion_chunks",
        embedding=embedding,
        max_results=5,
        doc_top_k=5,
        section_top_k=5,
        chunk_top_k=5,
        min_docs=0,
    )
    emb = embedding.embed(["hello world"])[0]
    tags = "alpha, beta"
    index.doc_collection.add(
        ids=["doc_meta"],
        embeddings=[emb],
        metadatas=[{"tenant_id": "tenant_meta", "doc_id": "doc_meta", "title": "Hello", "product": "p1", "version": "v1", "tags": tags}],
    )
    index.section_collection.add(
        ids=["doc_meta:sec1"],
        embeddings=[emb],
        metadatas=[
            {
                "tenant_id": "tenant_meta",
                "doc_id": "doc_meta",
                "section_id": "sec1",
                "summary": "hello summary",
                "page_start": 1,
                "page_end": 1,
                "chunk_ids": "chunk_1_1",
                "product": "p1",
                "version": "v1",
                "tags": tags,
            }
        ],
    )
    index.collection.add(
        ids=["doc_meta:chunk1"],
        embeddings=[emb],
        metadatas=[
            {
                "tenant_id": "tenant_meta",
                "doc_id": "doc_meta",
                "chunk_id": "chunk_1_1",
                "text": "hello world chunk",
                "product": "p1",
                "version": "v1",
                "tags": tags,
            }
        ],
    )
    query = RetrievalQuery(query="hello", tenant_id="tenant_meta", filters=RetrievalFilters(product="p1", tags=["alpha"]))
    hits, steps = index.search(query)
    assert hits
    assert hits[0].doc_id == "doc_meta"
    assert hits[0].anchor_chunk_id == "chunk_1_1"
    assert steps.chunks == []
