from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.tools.base import BaseTool


class ReadDocMetadataTool(BaseTool):
    name = "read_doc_metadata"

    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = arguments.get("doc_id")
        if not doc_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id required")
        return {"doc_id": str(doc_id)}

    async def run(self, arguments: Dict[str, Any], context):
        doc_id = arguments["doc_id"]
        metadata = self.repository.get_metadata(doc_id)
        if not metadata:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
        if metadata.tenant_id != context.user.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCESS_DENIED")
        return metadata.model_dump()
