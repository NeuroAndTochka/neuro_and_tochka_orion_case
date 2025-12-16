from __future__ import annotations

from typing import Any, Dict

import httpx
from fastapi import HTTPException, status
from mcp_tools_proxy.logging import get_logger


class RetrievalClient:
    """Lightweight client for Retrieval Service chunk window endpoint."""

    def __init__(self, chunk_window_url: str, timeout: float = 10.0, transport: httpx.BaseTransport | None = None) -> None:
        self.chunk_window_url = chunk_window_url.rstrip("/")
        self.timeout = timeout
        self._transport = transport
        self._logger = get_logger(__name__)

    async def fetch_chunk_window(
        self,
        *,
        tenant_id: str,
        doc_id: str,
        anchor_chunk_id: str,
        window_before: int,
        window_after: int,
    ) -> Dict[str, Any]:
        payload = {
            "tenant_id": tenant_id,
            "doc_id": doc_id,
            "anchor_chunk_id": anchor_chunk_id,
            "window_before": window_before,
            "window_after": window_after,
        }
        self._logger.info(
            "retrieval_chunk_window_request",
            url=self.chunk_window_url,
            doc_id=doc_id,
            anchor_chunk_id=anchor_chunk_id,
            before=window_before,
            after=window_after,
            tenant_id=tenant_id,
        )
        try:
            async with httpx.AsyncClient(transport=self._transport) as client:
                resp = await client.post(self.chunk_window_url, json=payload, timeout=self.timeout)
        except httpx.HTTPError as exc:  # pragma: no cover - network path
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"code": "retrieval_unavailable", "message": str(exc)},
            ) from exc

        body: Dict[str, Any] | None
        try:
            body = resp.json()
        except Exception:
            body = None

        if resp.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chunk_not_found")
        if resp.status_code == status.HTTP_400_BAD_REQUEST:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=body or "bad_request")
        if resp.is_error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"code": "retrieval_error", "status": resp.status_code, "message": body or resp.text},
            )
        if body is None:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="invalid_retrieval_response")
        self._logger.info(
            "retrieval_chunk_window_response",
            doc_id=doc_id,
            anchor_chunk_id=anchor_chunk_id,
            count=len(body.get("chunks", [])) if isinstance(body, dict) else None,
        )
        return body
