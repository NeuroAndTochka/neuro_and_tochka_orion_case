from fastapi import FastAPI

from mcp_tools_proxy.config import get_settings
from mcp_tools_proxy.core.executor import ToolRegistry
from mcp_tools_proxy.logging import configure_logging
from mcp_tools_proxy.routers import mcp

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.include_router(mcp.router)
app.state.tool_registry = ToolRegistry(settings)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
