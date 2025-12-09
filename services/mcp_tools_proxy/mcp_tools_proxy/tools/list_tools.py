from __future__ import annotations

from typing import Any, Dict, List

from mcp_tools_proxy.tools.base import BaseTool


class ListToolsTool(BaseTool):
    name = "list_available_tools"

    def __init__(self, repository, settings, tool_names: List[str]):
        super().__init__(repository, settings)
        self.tool_names = tool_names

    def validate_args(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {}

    async def run(self, arguments: Dict[str, Any], context):
        return {"tools": self.tool_names}
