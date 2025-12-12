from __future__ import annotations

from typing import List, Sequence

import httpx
import structlog

from ingestion_service.config import Settings
from ingestion_service.core.parser import DocumentParser


class Summarizer:
    """Генератор кратких резюме секций через OpenAI-совместимое API (OpenRouter)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mock = settings.mock_mode or not settings.summary_api_base
        self._logger = structlog.get_logger(__name__)

    def summarize(self, texts: Sequence[str]) -> List[str]:
        if not texts:
            return []
        if self._mock:
            return [self._fallback(text) for text in texts]

        base = (self.settings.summary_api_base or "").rstrip("/")
        path = "/chat/completions" if base.endswith("/v1") else "/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.summary_api_key}"} if self.settings.summary_api_key else {}
        if self.settings.summary_referer:
            headers["HTTP-Referer"] = self.settings.summary_referer
        if self.settings.summary_title:
            headers["X-Title"] = self.settings.summary_title

        results: List[str] = []
        with httpx.Client(base_url=base, timeout=30.0) as client:
            for text in texts:
                try:
                    payload = {
                        "model": self.settings.summary_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Сделай короткое русскоязычное резюме секции документа (1-2 предложения). "
                                "Без воды, без списков, только факты.",
                            },
                            {"role": "user", "content": text[:4000]},
                        ],
                        "max_tokens": 120,
                        "temperature": 0.2,
                    }
                    resp = client.post(path, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    choice = data.get("choices", [{}])[0]
                    content = choice.get("message", {}).get("content") or ""
                    results.append(DocumentParser._clean_text(content) or self._fallback(text))
                except Exception as exc:
                    self._logger.warning("summary_fallback", reason=str(exc))
                    results.append(self._fallback(text))
        return results

    @staticmethod
    def _fallback(text: str) -> str:
        return DocumentParser._clean_text(text)[:200]
