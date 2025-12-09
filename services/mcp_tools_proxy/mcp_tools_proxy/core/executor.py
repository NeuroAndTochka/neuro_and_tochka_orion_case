from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.clients.documents import DocumentRepository
from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.core.rate_limit import ToolRateLimiter
from mcp_tools_proxy.schemas import MCPExecuteRequest, MCPExecuteResponse, MCPError, ToolExecutionContext
from mcp_tools_proxy.tools.base import BaseTool
from mcp_tools_proxy.tools.list_tools import ListToolsTool
from mcp_tools_proxy.tools.local_search import DocLocalSearchTool
from mcp_tools_proxy.tools.read_metadata import ReadDocMetadataTool
from mcp_tools_proxy.tools.read_pages import ReadDocPagesTool
from mcp_tools_proxy.tools.read_section import ReadDocSectionTool


class ToolRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(mock_mode=settings.mock_mode)
        self.tools: Dict[str, BaseTool] = {}
        self._init_tools()
        self.rate_limiter = ToolRateLimiter(settings.rate_limit_calls, settings.rate_limit_tokens)

    def _init_tools(self) -> None:
        tool_classes = [
            ReadDocSectionTool,
            ReadDocPagesTool,
            ReadDocMetadataTool,
            DocLocalSearchTool,
        ]
        for tool_cls in tool_classes:
            tool = tool_cls(self.repository, self.settings)
            self.tools[tool.name] = tool
        self.tools[ListToolsTool.name] = ListToolsTool(
            self.repository,
            self.settings,
            tool_names=sorted(self.tools.keys()),
        )

    async def execute(self, request: MCPExecuteRequest) -> MCPExecuteResponse:
        tool = self.tools.get(request.tool_name)
        if not tool:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tool_not_found")

        trace_id = request.trace_id or "trace-unknown"
        context = ToolExecutionContext(user=request.user, trace_id=trace_id)

        estimated_tokens = 100  # rough default; real implementation should estimate
        limiter_key = f"{request.user.tenant_id}:{request.arguments.get('doc_id','global')}"
        try:
            await self.rate_limiter.check(limiter_key, estimated_tokens)
            return await tool.execute(request.arguments, context)
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else exc.detail or {}
            if isinstance(detail, dict):
                code = detail.get("code", "TOOL_ERROR")
                message = detail.get("message") or str(detail)
            else:
                code = str(detail)
                message = str(detail)
            return MCPExecuteResponse(status="error", error=MCPError(code=code, message=message), trace_id=trace_id)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
