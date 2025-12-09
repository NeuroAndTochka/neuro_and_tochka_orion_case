from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.tools.base import BaseTool


class DocLocalSearchTool(BaseTool):
    name = "doc_local_search"

    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        doc_id = arguments.get("doc_id")
        query = arguments.get("query")
        max_results = int(arguments.get("max_results", 3))
        if not doc_id or not query:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="doc_id and query required")
        if max_results > 5:
            max_results = 5
        return {"doc_id": str(doc_id), "query": str(query), "max_results": max_results}

    async def run(self, arguments: Dict[str, Any], context):
        doc_id = arguments["doc_id"]
        self._check_doc_access(doc_id, context.user.tenant_id)
        snippets = self.repository.local_search(doc_id, arguments["query"], arguments["max_results"])
        if not snippets:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no_snippets_found")
        for snippet in snippets:
            snippet["snippet"] = snippet["snippet"][: self.settings.max_text_bytes // arguments["max_results"]]
        return {"snippets": snippets, "count": len(snippets), "doc_id": doc_id}
