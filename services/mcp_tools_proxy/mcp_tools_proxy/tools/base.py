from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.clients.documents import DocumentRepository
from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.schemas import MCPExecuteResponse, ToolExecutionContext


class BaseTool(ABC):
    name: str

    def __init__(self, repository: DocumentRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    @abstractmethod
    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def run(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        ...

    def _check_doc_access(self, doc_id: str, tenant_id: str) -> None:
        metadata = self.repository.get_metadata(doc_id)
        if metadata is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="document_not_found")
        if metadata.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ACCESS_DENIED")

    async def execute(self, arguments: Dict[str, Any], context: ToolExecutionContext) -> MCPExecuteResponse:
        params = self.validate_args(arguments)
        result = await self.run(params, context)
        return MCPExecuteResponse(status="ok", result=result, trace_id=context.trace_id)
