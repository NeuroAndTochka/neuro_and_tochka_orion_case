from __future__ import annotations

from typing import Dict, List

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.config import Settings


class RetrievalClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def search(self, query_payload: Dict[str, str]) -> List[Dict[str, str]]:
        if self.settings.mock_mode:
            return [
                {
                    "doc_id": "doc_1",
                    "section_id": "sec_intro",
                    "text": "LDAP intro...",
                    "page_start": 1,
                    "page_end": 2,
                }
            ]
        if not self.settings.retrieval_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="retrieval url missing")
        response = await self.http_client.post(self.settings.retrieval_url, json=query_payload, timeout=10)
        response.raise_for_status()
        return response.json()
