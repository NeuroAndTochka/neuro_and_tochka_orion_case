from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.clients.retrieval import RetrievalClient
from mcp_tools_proxy.logging import get_logger
from mcp_tools_proxy.tools.base import BaseTool


class ReadChunkWindowTool(BaseTool):
    """Fetches a window of chunks around an anchor chunk via Retrieval Service."""

    name = "read_chunk_window"

    def __init__(self, repository, settings, retrieval_client: RetrievalClient | None) -> None:
        super().__init__(repository, settings)
        self.retrieval_client = retrieval_client
        self._logger = get_logger(__name__)

    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = arguments.get("doc_id")
        anchor_id = arguments.get("anchor_chunk_id")
        if not doc_id or not anchor_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id and anchor_chunk_id are required")
        before = int(arguments.get("window_before", 0))
        after = int(arguments.get("window_after", 0))
        if before < 0 or after < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="window_before/window_after must be >= 0")
        limit = max(1, getattr(self.settings, "max_chunk_window", 5))
        if before + after + 1 > limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WINDOW_TOO_LARGE", "message": f"Requested {before+after+1} chunks, limit is {limit}"},
            )
        return {
            "doc_id": str(doc_id),
            "anchor_chunk_id": str(anchor_id),
            "window_before": before,
            "window_after": after,
        }

    async def run(self, arguments: Dict[str, Any], context):
        doc_id = arguments["doc_id"]
        anchor_id = arguments["anchor_chunk_id"]
        before = arguments["window_before"]
        after = arguments["window_after"]
        # try to enforce tenant using local metadata if available; Retrieval service still filters by tenant_id
        try:
            self._check_doc_access(doc_id, context.user.tenant_id)
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND or self.settings.mock_mode:
                raise
        if not self.retrieval_client:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="retrieval_client_not_configured")

        self._logger.info(
            "chunk_window_call",
            doc_id=doc_id,
            anchor_chunk_id=anchor_id,
            before=before,
            after=after,
            tenant_id=context.user.tenant_id,
            trace_id=context.trace_id,
        )
        response = await self.retrieval_client.fetch_chunk_window(
            tenant_id=context.user.tenant_id,
            doc_id=doc_id,
            anchor_chunk_id=anchor_id,
            window_before=before,
            window_after=after,
        )
        chunks = response.get("chunks") if isinstance(response, dict) else None
        if not chunks:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chunks_not_found")

        remaining_bytes = self.settings.max_text_bytes
        trimmed = []
        for chunk in chunks:
            if remaining_bytes <= 0:
                break
            text = chunk.get("text") or ""
            allowed_text = text[:remaining_bytes]
            remaining_bytes -= len(allowed_text)
            trimmed.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "page": chunk.get("page"),
                    "chunk_index": chunk.get("chunk_index"),
                    "text": allowed_text,
                }
            )
        total_text_len = sum(len(c.get("text") or "") for c in trimmed)
        tokens = min(self.settings.rate_limit_tokens, total_text_len // 4 if total_text_len else 0)
        self._logger.info(
            "chunk_window_return",
            doc_id=doc_id,
            anchor_chunk_id=anchor_id,
            returned=len(trimmed),
            tokens=tokens,
            trace_id=context.trace_id,
        )
        return {
            "doc_id": doc_id,
            "anchor_chunk_id": anchor_id,
            "window_before": before,
            "window_after": after,
            "chunks": trimmed,
            "count": len(trimmed),
            "tokens": tokens,
        }
