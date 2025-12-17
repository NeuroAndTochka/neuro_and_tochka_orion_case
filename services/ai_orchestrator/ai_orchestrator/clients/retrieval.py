from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.config import Settings


class RetrievalClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def search(self, query_payload: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, int]]]:
        if self.settings.mock_mode:
            return (
                self._sanitize_hits(
                    [
                        {
                            "doc_id": "doc_1",
                            "section_id": "sec_intro",
                            "summary": "LDAP intro...",
                            "score": 0.98,
                            "page_start": 1,
                            "page_end": 2,
                        }
                    ]
                ),
                None,
            )
        if not self.settings.retrieval_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="retrieval url missing")
        response = await self.http_client.post(self.settings.retrieval_url, json=query_payload)
        response.raise_for_status()
        payload = response.json()
        steps_info: Optional[Dict[str, int]] = None
        if isinstance(payload, dict):
            hits = payload.get("hits", [])
            steps = payload.get("steps")
            if isinstance(steps, dict):
                steps_info = {
                    "docs": len(steps.get("docs") or []),
                    "sections": len(steps.get("sections") or []),
                    "chunks": len(steps.get("chunks") or []),
                }
            if isinstance(hits, list):
                return self._sanitize_hits(hits), steps_info
        if isinstance(payload, list):
            return self._sanitize_hits(payload), steps_info
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="retrieval response format invalid")

    def _sanitize_hits(self, raw_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned: List[Dict[str, Any]] = []
        for raw in raw_hits:
            if not isinstance(raw, dict):
                continue
            safe = {k: v for k, v in raw.items() if k != "text"}
            if not safe.get("summary"):
                title = raw.get("title")
                if title:
                    safe["summary"] = title
            cleaned.append(safe)
        return cleaned
