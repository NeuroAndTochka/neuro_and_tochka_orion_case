from __future__ import annotations

from typing import Dict

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.config import Settings


class LLMClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def generate(self, payload: Dict) -> Dict:
        if self.settings.mock_mode:
            return {
                "answer": "Mock answer with context",
                "used_tokens": {"prompt": 100, "completion": 50},
                "tools_called": [],
                "meta": {"model_name": "mock", "tool_steps": 0},
                "sources": [
                    {
                        "doc_id": "doc_1",
                        "section_id": "sec_intro",
                        "page_start": 1,
                        "page_end": 2,
                    }
                ],
            }
        if not self.settings.llm_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="llm url missing")
        response = await self.http_client.post(self.settings.llm_url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
