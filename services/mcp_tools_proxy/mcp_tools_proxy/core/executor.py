from __future__ import annotations

import json
from typing import Dict

from fastapi import HTTPException, status

from mcp_tools_proxy.clients.documents import DocumentRepository
from mcp_tools_proxy.clients.retrieval import RetrievalClient
from mcp_tools_proxy.config import Settings
from mcp_tools_proxy.core.rate_limit import ToolRateLimiter
from mcp_tools_proxy.logging import get_logger
from mcp_tools_proxy.schemas import MCPExecuteRequest, MCPExecuteResponse, MCPError, ToolExecutionContext
from mcp_tools_proxy.tools.base import BaseTool
from mcp_tools_proxy.tools.chunk_window import ReadChunkWindowTool
from mcp_tools_proxy.tools.list_tools import ListToolsTool
from mcp_tools_proxy.tools.local_search import DocLocalSearchTool
from mcp_tools_proxy.tools.read_metadata import ReadDocMetadataTool
from mcp_tools_proxy.tools.read_pages import ReadDocPagesTool
from mcp_tools_proxy.tools.read_section import ReadDocSectionTool


class ToolRegistry:
    def __init__(self, settings: Settings, retrieval_client: RetrievalClient | None = None) -> None:
        self.settings = settings
        self.repository = DocumentRepository(mock_mode=settings.mock_mode)
        self.retrieval_client = retrieval_client or (
            RetrievalClient(settings.retrieval_window_url, timeout=settings.retrieval_timeout)
            if settings.retrieval_window_url
            else None
        )
        self.tools: Dict[str, BaseTool] = {}
        self._init_tools()
        self.rate_limiter = ToolRateLimiter(settings.rate_limit_calls, settings.rate_limit_tokens)
        self._logger = get_logger(__name__)

    def _init_tools(self) -> None:
        tool_classes = [
            ReadDocSectionTool,
            ReadDocPagesTool,
            ReadDocMetadataTool,
            DocLocalSearchTool,
            ReadChunkWindowTool,
        ]
        for tool_cls in tool_classes:
            if tool_cls is ReadChunkWindowTool:
                tool = tool_cls(self.repository, self.settings, self.retrieval_client)
            else:
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
        self._logger.info(
            "mcp_tool_invocation",
            tool=request.tool_name,
            tenant_id=request.user.tenant_id,
            user_id=request.user.user_id,
            trace_id=trace_id,
            args=list(request.arguments.keys()),
        )

        estimated_tokens = 100  # rough default; real implementation should estimate
        limiter_key = f"{request.user.tenant_id}:{request.arguments.get('doc_id','global')}"
        try:
            await self.rate_limiter.check(limiter_key, estimated_tokens)
            response = await tool.execute(request.arguments, context)
            self._logger.info(
                "mcp_tool_completed",
                tool=request.tool_name,
                status=response.status,
                trace_id=trace_id,
                tokens=(response.result or {}).get("tokens") if response.result else None,
            )
            return response
        except HTTPException as exc:
            detail = exc.detail if exc.detail is not None else {}
            code = "TOOL_ERROR"
            raw_message = detail
            if isinstance(detail, dict):
                code = detail.get("code", code)
                raw_message = detail.get("message", detail)
            if not isinstance(raw_message, str):
                try:
                    message = json.dumps(raw_message, ensure_ascii=False)
                except Exception:
                    message = str(raw_message)
            else:
                message = raw_message
            self._logger.warning(
                "mcp_tool_error",
                tool=request.tool_name,
                code=code,
                message=message,
                status_code=exc.status_code,
                trace_id=trace_id,
            )
            return MCPExecuteResponse(status="error", error=MCPError(code=code, message=message), trace_id=trace_id)
        except Exception as exc:  # pragma: no cover
            self._logger.error(
                "mcp_tool_exception",
                tool=request.tool_name,
                error=str(exc),
                trace_id=trace_id,
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
