import json
from typing import Tuple

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openwebui_adapter.clients.gateway import GatewayClient
from openwebui_adapter.config import Settings
from openwebui_adapter.routers import openai
from openwebui_adapter.schemas import ChatMessage
from openwebui_adapter.utils import build_query_from_messages


def build_app_with_transport(transport: httpx.BaseTransport, settings: Settings | None = None) -> Tuple[FastAPI, Settings]:
    settings = settings or Settings(auth_mode="static_token", static_bearer_token="test-token", gateway_base_url="http://gateway.local")
    client = httpx.AsyncClient(transport=transport, base_url=settings.gateway_base_url)
    app = FastAPI()
    app.state.gateway_client = GatewayClient(settings, client)
    app.state.settings = settings
    app.dependency_overrides[openai.get_settings] = lambda: settings
    app.include_router(openai.router)
    return app, settings


def test_query_builder_with_system_prefix():
    messages = [
        ChatMessage(role="system", content="You are Orion"),
        ChatMessage(role="assistant", content="Previous reply"),
        ChatMessage(role="user", content="Tell me more"),
    ]
    query = build_query_from_messages(messages, max_prefix_chars=200)
    assert query.startswith("SYSTEM: You are Orion")
    assert "ASSISTANT: Previous reply" in query
    assert query.endswith("USER: Tell me more")


def test_models_endpoint_returns_default_model():
    from openwebui_adapter.main import app

    with TestClient(app) as client:
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert data["data"][0]["id"]


@pytest.mark.anyio
async def test_chat_completions_success_roundtrip():
    trace_id = "trace-abc"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/api/v1/assistant/query"
        assert payload["context"]["channel"] == "openwebui"
        return httpx.Response(200, json={"answer": "Here is your answer", "sources": [{"doc_id": "doc1"}], "meta": {"trace_id": trace_id}})

    transport = httpx.MockTransport(handler)
    app, settings = build_app_with_transport(transport, Settings(auth_mode="static_token", static_bearer_token="secret", gateway_base_url="http://gateway.local"))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://adapter") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": settings.default_model_id, "messages": [{"role": "user", "content": "hi"}]},
        )
    await app.state.gateway_client.http_client.aclose()
    assert resp.status_code == 200
    assert resp.headers["X-Trace-Id"] == trace_id
    body = resp.json()
    assert body["choices"][0]["message"]["content"] == "Here is your answer"
    assert body["id"].startswith("chatcmpl-")


@pytest.mark.anyio
async def test_chat_completions_streaming_chunks():
    trace_id = "trace-stream"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"answer": "streamed", "meta": {"trace_id": trace_id}})

    transport = httpx.MockTransport(handler)
    app, settings = build_app_with_transport(transport)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://adapter") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": settings.default_model_id, "messages": [{"role": "user", "content": "hi"}], "stream": True},
        )
    await app.state.gateway_client.http_client.aclose()
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    chunks = [line for line in resp.text.splitlines() if line.startswith("data: ")]
    assert chunks[-1] == "data: [DONE]"


@pytest.mark.anyio
async def test_gateway_400_translated():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": {"code": "validation_error", "reason": "bad payload"}})

    transport = httpx.MockTransport(handler)
    app, settings = build_app_with_transport(transport)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://adapter") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": settings.default_model_id, "messages": [{"role": "user", "content": "hi"}]},
        )
    await app.state.gateway_client.http_client.aclose()
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"]["details"]["code"] == "validation_error"


@pytest.mark.anyio
async def test_gateway_unauthorized_passed_through():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": {"code": "auth_failed"}})

    transport = httpx.MockTransport(handler)
    app, settings = build_app_with_transport(transport)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://adapter") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": settings.default_model_id, "messages": [{"role": "user", "content": "hi"}]},
        )
    await app.state.gateway_client.http_client.aclose()
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["type"] == "authentication_error"


@pytest.mark.anyio
async def test_gateway_timeout_returns_504():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("boom")

    transport = httpx.MockTransport(handler)
    app, settings = build_app_with_transport(transport)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://adapter") as client:
        resp = await client.post(
            "/v1/chat/completions",
            json={"model": settings.default_model_id, "messages": [{"role": "user", "content": "hi"}]},
        )
    await app.state.gateway_client.http_client.aclose()
    assert resp.status_code == 504
    assert resp.json()["error"]["type"] == "server_error"
