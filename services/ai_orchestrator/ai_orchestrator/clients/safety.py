from __future__ import annotations

from typing import Dict

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.config import Settings


class SafetyClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def check_output(self, payload: Dict[str, str]) -> Dict[str, str]:
        if self.settings.mock_mode:
            return {"status": "allowed"}
        if not self.settings.safety_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="safety url missing")
        response = await self.http_client.post(self.settings.safety_url, json=payload)
        response.raise_for_status()
        return response.json()
