from __future__ import annotations

from typing import Any, Dict

import httpx
from fastapi import HTTPException, status

from llm_service.config import Settings


class MCPClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def execute(self, tool_name: str, arguments: Dict[str, Any], user: Dict[str, Any], trace_id: str | None) -> Dict[str, Any]:
        if self.settings.mock_mode:
            return {"status": "ok", "result": {"text": "Mock snippet", "doc_id": arguments.get("doc_id")}, "trace_id": trace_id}
        if not self.settings.mcp_proxy_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MCP proxy URL missing")
        payload = {
            "tool_name": tool_name,
            "arguments": arguments,
            "user": user,
            "trace_id": trace_id,
        }
        try:
            response = await self.http_client.post(self.settings.mcp_proxy_url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"mcp proxy error: {exc}") from exc
