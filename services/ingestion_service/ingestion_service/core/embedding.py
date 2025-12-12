from __future__ import annotations

import hashlib
from typing import Iterable, List, Sequence

import httpx

from ingestion_service.config import Settings


class EmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mock = settings.mock_mode or not settings.embedding_api_base

    def embed(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._mock:
            return [self._pseudo_embedding(text) for text in texts]
        headers = {"Authorization": f"Bearer {self.settings.embedding_api_key}"} if self.settings.embedding_api_key else {}
        payload = {"model": self.settings.embedding_model, "input": list(texts)}
        with httpx.Client(base_url=self.settings.embedding_api_base, timeout=15.0) as client:
            resp = client.post("/v1/embeddings", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return [item["embedding"] for item in data.get("data", [])]

    @staticmethod
    def _pseudo_embedding(text: str, dim: int = 8) -> List[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        return [int.from_bytes(h[i : i + 4], "big") % 1000 / 1000.0 for i in range(0, dim * 4, 4)]
