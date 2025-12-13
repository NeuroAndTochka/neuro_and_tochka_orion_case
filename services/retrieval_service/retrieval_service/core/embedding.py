from __future__ import annotations

import hashlib
import time
from typing import List, Sequence

import httpx
import structlog

from retrieval_service.config import Settings


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mock = settings.mock_mode or not settings.embedding_api_base
        self._logger = structlog.get_logger(__name__)
        self.max_attempts = max(1, settings.embedding_max_attempts)
        self.retry_delay = settings.embedding_retry_delay_seconds

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._mock:
            self._logger.info("retrieval_embedding_mock", items=len(texts))
            return [self._pseudo_embedding(text) for text in texts]

        headers = {"Authorization": f"Bearer {self.settings.embedding_api_key}"} if self.settings.embedding_api_key else {}
        base = (self.settings.embedding_api_base or "").rstrip("/")
        path = "/embeddings" if base.endswith("/v1") else "/v1/embeddings"
        payload = {"model": self.settings.embedding_model, "input": list(texts), "encoding_format": "float"}
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            started = time.perf_counter()
            try:
                with httpx.Client(base_url=base, timeout=20.0) as client:
                    self._logger.info(
                        "retrieval_embedding_request",
                        url=base + path,
                        model=self.settings.embedding_model,
                        items=len(texts),
                        attempt=attempt,
                    )
                    resp = client.post(path, json=payload, headers=headers)
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    self._logger.info(
                        "retrieval_embedding_response",
                        status_code=resp.status_code,
                        model=self.settings.embedding_model,
                        items=len(texts),
                        latency_ms=latency_ms,
                        attempt=attempt,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return [item["embedding"] for item in data.get("data", [])]
            except Exception as exc:  # pragma: no cover - network errors
                last_error = exc
                self._logger.warning("retrieval_embedding_attempt_failed", attempt=attempt, error=str(exc))
                if attempt < self.max_attempts:
                    time.sleep(self.retry_delay)
        self._logger.error("retrieval_embedding_fallback", reason=str(last_error) if last_error else "unknown")
        return [self._pseudo_embedding(text) for text in texts]

    @staticmethod
    def _pseudo_embedding(text: str, dim: int = 8) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [int.from_bytes(h[i : i + 4], "big") % 1000 / 1000.0 for i in range(0, dim * 4, 4)]
