from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status

from llm_service.config import Settings


@dataclass
class LLMRuntimeResult:
    type: str  # "message" or "tool_call"
    content: Optional[str]
    tool_name: Optional[str]
    tool_arguments: Optional[Dict[str, Any]]
    usage: Dict[str, int]


class LLMRuntimeClient:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def chat_completion(self, payload: Dict[str, Any]) -> LLMRuntimeResult:
        if self.settings.mock_mode:
            return self._mock_response(payload)
        if not self.settings.llm_runtime_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM runtime URL not configured")
        try:
            response = await self.http_client.post(self.settings.llm_runtime_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            return self._map_choice(choice, data.get("usage", {}))
        except httpx.HTTPError as exc:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"llm runtime error: {exc}") from exc

    def _mock_response(self, payload: Dict[str, Any]) -> LLMRuntimeResult:
        messages: List[Dict[str, str]] = payload.get("messages", [])
        last = messages[-1]
        content = last.get("content", "")
        if "TOOL_CALL" in content.upper():
            return LLMRuntimeResult(
                type="tool_call",
                content=None,
                tool_name="read_doc_section",
                tool_arguments={"doc_id": "doc_1", "section_id": "sec_intro"},
                usage={"prompt_tokens": 200, "completion_tokens": 50},
            )
        combined_context = " ".join(chunk.get("text", "") for chunk in payload.get("context", []))
        answer = f"Mock answer referencing context: {combined_context[:120]}" if combined_context else "Mock answer"
        return LLMRuntimeResult(
            type="message",
            content=answer,
            tool_name=None,
            tool_arguments=None,
            usage={"prompt_tokens": 150, "completion_tokens": 60},
        )

    def _map_choice(self, choice: Dict[str, Any], usage: Dict[str, Any]) -> LLMRuntimeResult:
        message = choice.get("message", {})
        tool_call = message.get("tool_calls", [{}])[-1] if message.get("tool_calls") else None
        if tool_call:
            arguments = tool_call.get("function", {}).get("arguments", "{}")
            return LLMRuntimeResult(
                type="tool_call",
                content=None,
                tool_name=tool_call.get("function", {}).get("name"),
                tool_arguments=arguments,
                usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)},
            )
        return LLMRuntimeResult(
            type="message",
            content=message.get("content"),
            tool_name=None,
            tool_arguments=None,
            usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)},
        )
