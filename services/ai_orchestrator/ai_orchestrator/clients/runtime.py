from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException, status

from ai_orchestrator.config import Settings


@dataclass
class RuntimeResult:
    type: str  # "message" or "tool_call"
    content: Optional[str]
    tool_name: Optional[str]
    tool_arguments: Optional[Dict[str, Any]]
    usage: Dict[str, int]


class LLMRuntimeClient:
    """Thin wrapper around OpenAI-style chat completions."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def chat_completion(self, payload: Dict[str, Any]) -> RuntimeResult:
        if self.settings.mock_mode:
            return self._mock_response(payload)
        runtime_url = self._resolve_url()
        if not runtime_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM runtime URL not configured")
        try:
            headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"} if self.settings.llm_api_key else None
            response = await self.http_client.post(runtime_url, json=payload, headers=headers)
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:  # pragma: no cover - runtime path
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"llm runtime returned non-JSON response: {response.text[:200]}",
                ) from exc
            choice = data.get("choices", [{}])[0]
            return self._map_choice(choice, data.get("usage", {}))
        except httpx.HTTPError as exc:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"llm runtime error: {exc}") from exc

    def _resolve_url(self) -> str | None:
        url = self.settings.llm_runtime_url
        if not url:
            return None
        stripped = url.rstrip("/")
        if stripped.endswith("/api/v1"):
            return f"{stripped}/chat/completions"
        return url

    def _mock_response(self, payload: Dict[str, Any]) -> RuntimeResult:
        messages = payload.get("messages", [])
        # If last tool result was added, return final answer
        last_msg = messages[-1] if messages else {}
        if last_msg.get("role") == "assistant" and str(last_msg.get("content", "")).startswith("TOOL_RESULT"):
            return RuntimeResult(
                type="message",
                content="Mock final answer after tool results.",
                tool_name=None,
                tool_arguments=None,
                usage={"prompt_tokens": 120, "completion_tokens": 40},
            )
        # Simulate requesting a section text via tool call
        return RuntimeResult(
            type="tool_call",
            content=None,
            tool_name="read_chunk_window",
            tool_arguments={"doc_id": "doc_1", "section_id": "sec_intro"},
            usage={"prompt_tokens": 80, "completion_tokens": 20},
        )

    def _map_choice(self, choice: Dict[str, Any], usage: Dict[str, Any]) -> RuntimeResult:
        message = choice.get("message", {})
        tool_call = message.get("tool_calls", [{}])[-1] if message.get("tool_calls") else None
        if tool_call:
            raw_args = tool_call.get("function", {}).get("arguments", "{}")
            arguments: Dict[str, Any]
            if isinstance(raw_args, str):
                try:
                    arguments = json.loads(raw_args)
                except Exception:
                    arguments = {}
            elif isinstance(raw_args, dict):
                arguments = raw_args
            else:
                arguments = {}
            return RuntimeResult(
                type="tool_call",
                content=None,
                tool_name=tool_call.get("function", {}).get("name"),
                tool_arguments=arguments,
                usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)},
            )
        return RuntimeResult(
            type="message",
            content=message.get("content"),
            tool_name=None,
            tool_arguments=None,
            usage={"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)},
        )
