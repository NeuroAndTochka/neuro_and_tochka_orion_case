from fastapi import APIRouter, Depends, Request

from mcp_tools_proxy.core.executor import ToolRegistry
from mcp_tools_proxy.schemas import MCPExecuteRequest, MCPExecuteResponse

router = APIRouter(prefix="/internal/mcp", tags=["mcp"])


def get_registry(request: Request) -> ToolRegistry:
    registry = getattr(request.app.state, "tool_registry", None)
    if registry is None:
        raise RuntimeError("Tool registry is not initialized")
    return registry


@router.post("/execute", response_model=MCPExecuteResponse)
async def execute_tool(
    request_body: MCPExecuteRequest,
    registry: ToolRegistry = Depends(get_registry),
) -> MCPExecuteResponse:
    return await registry.execute(request_body)
