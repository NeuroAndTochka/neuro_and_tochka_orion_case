from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from openwebui_adapter.config import Settings
from openwebui_adapter.logging import get_logger
from openwebui_adapter.schemas import GatewayAssistantRequest

logger = get_logger(__name__)


class GatewayClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient):
        self.settings = settings
        self.http_client = http_client
        path = settings.gateway_assistant_path or "/api/v1/assistant/query"
        self.assistant_path = path if path.startswith("/") else f"/{path}"

    async def query(self, payload: GatewayAssistantRequest, authorization: str | None) -> httpx.Response:
        headers = {}
        if authorization:
            headers["Authorization"] = authorization
        timeout = self.settings.http_timeout_seconds
        try:
            if timeout is not None:
                response = await self.http_client.post(
                    self.assistant_path,
                    json=payload.model_dump(exclude_none=True),
                    headers=headers,
                    timeout=timeout,
                )
            else:
                response = await self.http_client.post(
                    self.assistant_path,
                    json=payload.model_dump(exclude_none=True),
                    headers=headers,
                )
        except httpx.TimeoutException:
            logger.error("gateway.timeout")
            raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Gateway timeout")
        except httpx.HTTPError as exc:
            logger.error("gateway.request_failed", error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gateway request failed") from exc
        return response
