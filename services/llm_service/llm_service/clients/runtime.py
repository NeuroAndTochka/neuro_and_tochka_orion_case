from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
import structlog
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
        self._logger = structlog.get_logger(__name__)

    async def chat_completion(self, payload: Dict[str, Any]) -> LLMRuntimeResult:
        if self.settings.mock_mode:
            return self._mock_response(payload)
        runtime_url = self._resolve_url()
        if not runtime_url:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM runtime URL not configured")
        headers = self._build_auth_headers()
        try:
            response = await self.http_client.post(runtime_url, json=payload, headers=headers)
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:  # pragma: no cover - runtime path
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"llm runtime returned non-JSON response: {response.text[:200]}",
                ) from exc
            choice = data["choices"][0]
            return self._map_choice(choice, data.get("usage", {}))
        except httpx.HTTPStatusError as exc:  # pragma: no cover
            body = exc.response.text if exc.response else ""
            self._logger.error(
                "llm_runtime_http_error",
                status_code=exc.response.status_code if exc.response else None,
                body=body[:500] if body else None,
            )
            detail = body or str(exc)
            raise HTTPException(status_code=exc.response.status_code if exc.response else status.HTTP_502_BAD_GATEWAY, detail=f"llm runtime error: {detail}") from exc
        except httpx.HTTPError as exc:  # pragma: no cover
            self._logger.error("llm_runtime_error", error=str(exc))
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"llm runtime error: {exc}") from exc

    def _resolve_url(self) -> str | None:
        url = self.settings.llm_runtime_url
        if not url:
            return None
        stripped = url.rstrip("/")
        # If user passed base /api/v1, append chat/completions automatically
        if stripped.endswith("/api/v1"):
            return f"{stripped}/chat/completions"
        return url

    def _build_auth_headers(self) -> Dict[str, str]:
        api_key = (
            self.settings.runtime_api_key
            or os.getenv("LLM_RUNTIME_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("INGEST_SUMMARY_API_KEY")
        )
        if not api_key:
            self._logger.error("llm_runtime_api_key_missing")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM runtime API key missing")
        return {"Authorization": f"Bearer {api_key}"}

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
