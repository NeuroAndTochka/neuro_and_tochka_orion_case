from __future__ import annotations

import hashlib
from typing import Iterable

from fastapi import HTTPException, status

from openwebui_adapter.schemas import ChatCompletionRequest, ChatMessage, MessageContent


def extract_text(content: MessageContent) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if "text" in item and isinstance(item["text"], str):
                parts.append(item["text"])
            elif item.get("type") == "text" and isinstance(item.get("value"), str):
                parts.append(item["value"])
        return " ".join(parts)
    return str(content)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def build_query_from_messages(messages: Iterable[ChatMessage], max_prefix_chars: int = 2000) -> str:
    messages_list = list(messages)
    last_user = next((msg for msg in reversed(messages_list) if msg.role == "user"), None)
    if not last_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No user message found")

    user_text = extract_text(last_user.content).strip()
    if not user_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty user message")

    system_parts = [extract_text(msg.content).strip() for msg in messages_list if msg.role == "system"]
    history_parts = []
    for msg in messages_list:
        if msg is last_user:
            continue
        if msg.role in {"assistant", "user"}:
            text = extract_text(msg.content).strip()
            if text:
                history_parts.append(f"{msg.role.upper()}: {text}")

    prefix_sections: list[str] = []
    if system_parts:
        system_text = " ".join(part for part in system_parts if part)
        if system_text:
            prefix_sections.append(f"SYSTEM: {system_text}")
    if history_parts:
        context_text = "\n".join(history_parts[-3:])
        if context_text:
            prefix_sections.append(f"CONTEXT:\n{context_text}")

    prefix = "\n".join(prefix_sections).strip()
    if prefix:
        prefix = _truncate(prefix, max_prefix_chars)
        return f"{prefix}\nUSER: {user_text}"
    return user_text


def derive_conversation_id(header_value: str | None, payload: ChatCompletionRequest, authorization: str | None) -> str:
    if header_value:
        return header_value
    seed = payload.user or authorization or "anonymous"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:24]
    return f"conv_{digest}"


def chunk_answer(answer: str, size: int) -> list[str]:
    if size <= 0:
        return [answer]
    chunks: list[str] = []
    start = 0
    while start < len(answer):
        end = min(start + size, len(answer))
        chunks.append(answer[start:end])
        start = end
    return chunks or [answer]
