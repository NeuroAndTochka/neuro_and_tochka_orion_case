from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from api_gateway.clients.base import DownstreamClient


class OrchestratorClient(DownstreamClient):
    async def query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.mock_mode:
            return {
                "answer": "Mock answer from orchestrator",
                "sources": [],
                "meta": {"latency_ms": 1, "trace_id": payload.get("trace_id"), "safety": {"input": "allowed"}},
            }
        try:
            response = await self.post_json("/internal/orchestrator/respond", payload)
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"orchestrator error: {exc}") from exc
        return response.json()
