from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.tools.base import BaseTool


class ReadDocSectionTool(BaseTool):
    name = "read_doc_section"

    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = arguments.get("doc_id")
        section_id = arguments.get("section_id")
        if not doc_id or not section_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id and section_id are required")
        return {"doc_id": str(doc_id), "section_id": str(section_id)}

    async def run(self, arguments: Dict[str, Any], context):
        doc_id = arguments["doc_id"]
        section_id = arguments["section_id"]
        self._check_doc_access(doc_id, context.user.tenant_id)
        content = self.repository.read_section_text(doc_id, section_id)
        if not content:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
        trimmed = content[: self.settings.max_text_bytes]
        return {
            "text": trimmed,
            "tokens": min(len(trimmed) // 4, self.settings.rate_limit_tokens),
            "section_id": section_id,
            "doc_id": doc_id,
        }
