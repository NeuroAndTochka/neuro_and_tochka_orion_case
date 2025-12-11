import importlib
import os
import pathlib
import sys
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICE_DIRS = [
    "services/api_gateway",
    "services/safety_service",
    "services/ai_orchestrator",
    "services/llm_service",
    "services/mcp_tools_proxy",
    "services/retrieval_service",
]
for directory in SERVICE_DIRS:
    sys.path.append(str(ROOT / directory))


class HostRouterTransport(httpx.AsyncBaseTransport):
    def __init__(self, app_map: dict[str, FastAPI]) -> None:
        self.transports = {
            host: httpx.ASGITransport(app=app) for host, app in app_map.items()
        }

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        transport = self.transports.get(request.url.host)
        if transport is None:
            raise RuntimeError(f"Unknown host {request.url.host}")
        return await transport.handle_async_request(request)


def load_app(module_name: str, config_module) -> FastAPI:
    config_module.get_settings.cache_clear()
    module = importlib.import_module(module_name)
    module = importlib.reload(module)
    return module.app


@asynccontextmanager
async def manage_lifespan(app: FastAPI):
    async with app.router.lifespan_context(app):
        yield


@pytest.mark.anyio
async def test_api_gateway_pipeline_end_to_end():
    from api_gateway import config as gateway_config
    from ai_orchestrator import config as orch_config
    from ai_orchestrator.core.orchestrator import Orchestrator as CoreOrchestrator
    from ai_orchestrator.schemas import OrchestratorRequest
    from llm_service import config as llm_config
    from llm_service.core.orchestrator import LLMOrchestrator as CoreLLMOrchestrator
    from mcp_tools_proxy import config as mcp_config
    from retrieval_service import config as retrieval_config
    from safety_service import config as safety_config

    safety_app = load_app("safety_service.main", safety_config)
    retrieval_app = load_app("retrieval_service.main", retrieval_config)
    mcp_app = load_app("mcp_tools_proxy.main", mcp_config)
    llm_app = load_app("llm_service.main", llm_config)
    orchestrator_app = load_app("ai_orchestrator.main", orch_config)
    gateway_app = load_app("api_gateway.main", gateway_config)

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(manage_lifespan(safety_app))
        await stack.enter_async_context(manage_lifespan(retrieval_app))
        await stack.enter_async_context(manage_lifespan(mcp_app))
        await stack.enter_async_context(manage_lifespan(llm_app))

        router_transport = HostRouterTransport(
            {
                "safety.local": safety_app,
                "retrieval.local": retrieval_app,
                "llm.local": llm_app,
                "mcp.local": mcp_app,
            }
        )

        orch_http_client = await stack.enter_async_context(
            httpx.AsyncClient(transport=router_transport)
        )
        orch_settings = orch_config.Settings(
            retrieval_url="http://retrieval.local/internal/retrieval/search",
            llm_url="http://llm.local/internal/llm/generate",
            safety_url="http://safety.local/internal/safety/output-check",
            mock_mode=False,
        )
        orchestrator = CoreOrchestrator(orch_settings, orch_http_client)

        llm_http_client = await stack.enter_async_context(
            httpx.AsyncClient(transport=router_transport)
        )
        llm_settings = llm_config.Settings(
            mcp_proxy_url="http://mcp.local/internal/mcp/execute", mock_mode=True
        )
        llm_app.state.orchestrator = CoreLLMOrchestrator(llm_settings, llm_http_client)

        safety_http_client = await stack.enter_async_context(
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app=safety_app),
                base_url="http://safety.local",
            )
        )

        class LocalSafetyClient:
            async def check_input(self, payload):
                resp = await safety_http_client.post(
                    "/internal/safety/input-check", json=payload
                )
                return resp.json()

        class LocalOrchestratorClient:
            async def query(self, payload):
                response = await orchestrator.respond(OrchestratorRequest(**payload))
                return response.model_dump()

        class LocalRateLimiter:
            async def check(self, key: str) -> None:
                return None

        from api_gateway.dependencies import (
            get_current_user,
            get_orchestrator_client,
            get_rate_limiter,
            get_safety_client,
        )
        from api_gateway.core.context import AuthenticatedUser

        gateway_app.dependency_overrides[get_safety_client] = (
            lambda: LocalSafetyClient()
        )
        gateway_app.dependency_overrides[get_orchestrator_client] = (
            lambda: LocalOrchestratorClient()
        )
        gateway_app.dependency_overrides[get_rate_limiter] = lambda: LocalRateLimiter()
        gateway_app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
            user_id="demo", username="demo", tenant_id="tenant_1", roles=["user"]
        )

        with TestClient(gateway_app) as client:
            resp = client.post(
                "/api/v1/assistant/query",
                json={"query": "Расскажи про LDAP", "language": "ru"},
                headers={"Authorization": "Bearer test"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["answer"]
            assert data["meta"]["trace_id"]
