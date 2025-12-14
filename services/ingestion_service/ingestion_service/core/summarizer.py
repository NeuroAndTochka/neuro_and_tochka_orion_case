from __future__ import annotations

import time
from typing import List, Sequence

import structlog

from ingestion_service.config import Settings
from ingestion_service.core.parser import DocumentParser

try:  # pragma: no cover - runtime dependency
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback if not installed
    OpenAI = None


class Summarizer:
    """Генератор кратких резюме через OpenAI клиент (поддерживает OpenRouter base_url)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mock = settings.mock_mode or not settings.summary_api_base
        self._logger = structlog.get_logger(__name__)
        self.system_prompt = (
            "Сделай короткое русскоязычное резюме секции документа (1-2 предложения). "
            "Без воды, без списков, только факты."
        )
        self.model = settings.summary_model
        self.max_tokens = 120
        self.use_roles = True
        self.timeout = 30.0

        self._client = None
        if not self._mock and OpenAI:
            default_headers = {}
            if settings.summary_referer:
                default_headers["HTTP-Referer"] = settings.summary_referer
            if settings.summary_title:
                default_headers["X-Title"] = settings.summary_title
            self._client = OpenAI(
                base_url=settings.summary_api_base,
                api_key=settings.summary_api_key,
                default_headers=default_headers or None,
            )

    def summarize(self, texts: Sequence[str]) -> List[str]:
        if not texts:
            return []
        if self._mock or not self._client:
            if not self._client and not self._mock:
                self._logger.warning(
                    "summary_fallback", reason="OpenAI client not initialized"
                )
            self._logger.info("summary_mock", items=len(texts), model=self.model)
            return [self._fallback(text) for text in texts]

        results: List[str] = []
        for text in texts:
            try:
                messages = self._build_messages(text)
                started = time.perf_counter()
                self._logger.info(
                    "summary_request",
                    model=self.model,
                    use_roles=self.use_roles,
                    prompt_chars=len(text),
                )
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    # max_tokens=self.max_tokens,
                    # temperature=0.2,
                    # timeout=self.timeout,
                )
                raw_content = (
                    resp.choices[0].message.content if resp and resp.choices else ""
                )
                self._logger.info(
                    "summary_raw_content", model=self.model, raw=raw_content
                )
                extracted = self._extract_text(raw_content)
                cleaned = DocumentParser._clean_text(extracted)
                latency_ms = int((time.perf_counter() - started) * 1000)
                if not cleaned:
                    fallback_text = self._fallback(text)
                    results.append(fallback_text)
                    self._logger.warning(
                        "summary_empty_response",
                        model=self.model,
                        latency_ms=latency_ms,
                        completion_chars=len(extracted or ""),
                        fallback_chars=len(fallback_text),
                    )
                else:
                    results.append(cleaned)
                    self._logger.info(
                        "summary_response",
                        status="ok",
                        model=self.model,
                        latency_ms=latency_ms,
                        completion_chars=len(cleaned),
                    )
            except Exception as exc:  # pragma: no cover - network path
                self._logger.warning(
                    "summary_fallback",
                    reason=str(exc),
                    model=self.model,
                    prompt_chars=len(text),
                )
                results.append(self._fallback(text))
        return results

    @staticmethod
    def _fallback(text: str) -> str:
        return DocumentParser._clean_text(text)[:200]

    def get_config(self) -> dict:
        return {
            "system_prompt": self.system_prompt,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "use_roles": self.use_roles,
        }

    def update_config(
        self,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        use_roles: bool | None = None,
    ) -> dict:
        if system_prompt is not None:
            self.system_prompt = system_prompt
        if model is not None:
            self.model = model
        if max_tokens is not None:
            self.max_tokens = max_tokens
        if use_roles is not None:
            self.use_roles = use_roles
        return self.get_config()

    def _build_messages(self, text: str) -> list[dict]:
        user_content = text[:4000]
        if self.use_roles:
            return [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_content},
            ]
        return [{"role": "user", "content": f"{self.system_prompt}\n\n{user_content}"}]

    @staticmethod
    def _extract_text(content) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("output_text") or ""
                    if isinstance(text, str):
                        parts.append(text)
                elif hasattr(block, "text"):
                    text_val = getattr(block, "text", "")
                    if isinstance(text_val, str):
                        parts.append(text_val)
            return "\n".join(parts)
        if hasattr(content, "text") and isinstance(getattr(content, "text"), str):
            return getattr(content, "text")
        return ""
