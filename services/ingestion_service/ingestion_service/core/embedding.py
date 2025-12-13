from __future__ import annotations

import hashlib
from typing import List, Sequence

import httpx
import structlog

from ingestion_service.config import Settings


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mock = settings.mock_mode or not settings.embedding_api_base
        self._logger = structlog.get_logger(__name__)

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._mock:
            return [self._pseudo_embedding(text) for text in texts]
        headers = {"Authorization": f"Bearer {self.settings.embedding_api_key}"} if self.settings.embedding_api_key else {}
        # OpenRouter уже содержит префикс /api/v1, поэтому выбираем суффикс динамически
        base = (self.settings.embedding_api_base or "").rstrip("/")
        path = "/embeddings" if base.endswith("/v1") else "/v1/embeddings"
        payload = {"model": self.settings.embedding_model, "input": list(texts), "encoding_format": "float"}
        with httpx.Client(base_url=base, timeout=20.0) as client:
            self._logger.debug("embedding_request", url=base + path, model=self.settings.embedding_model, items=len(texts))
            resp = client.post(path, json=payload, headers=headers)
            self._logger.debug("embedding_response", status_code=resp.status_code)
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data.get("data", [])]

    @staticmethod
    def _pseudo_embedding(text: str, dim: int = 8) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [int.from_bytes(h[i : i + 4], "big") % 1000 / 1000.0 for i in range(0, dim * 4, 4)]
