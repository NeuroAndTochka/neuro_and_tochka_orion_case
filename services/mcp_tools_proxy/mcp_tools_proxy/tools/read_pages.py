from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.tools.base import BaseTool


class ReadDocPagesTool(BaseTool):
    name = "read_doc_pages"

    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = arguments.get("doc_id")
        page_start = arguments.get("page_start")
        page_end = arguments.get("page_end")
        if not doc_id or page_start is None or page_end is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id/page_start/page_end required")
        page_start = int(page_start)
        page_end = int(page_end)
        if page_end - page_start + 1 > self.settings.max_pages_per_call:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="page span exceeds limit")
        return {"doc_id": str(doc_id), "page_start": page_start, "page_end": page_end}

    async def run(self, arguments: Dict[str, Any], context):
        doc_id = arguments["doc_id"]
        self._check_doc_access(doc_id, context.user.tenant_id)
        content = self.repository.read_pages(doc_id, arguments["page_start"], arguments["page_end"])
        if not content:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="pages_not_found")
        trimmed = content[: self.settings.max_text_bytes]
        return {
            "text": trimmed,
            "tokens": min(len(trimmed) // 4, self.settings.rate_limit_tokens),
            "page_start": arguments["page_start"],
            "page_end": arguments["page_end"],
            "doc_id": doc_id,
        }
