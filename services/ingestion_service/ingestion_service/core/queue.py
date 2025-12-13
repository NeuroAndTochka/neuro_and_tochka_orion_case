from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Optional

from redis import asyncio as aioredis  # type: ignore


@dataclass
class WorkItem:
    job_id: str
    tenant_id: str
    doc_id: str
    storage_uri: Optional[str]
    product: Optional[str] = None
    version: Optional[str] = None
    tags: Optional[str] = None
    attempt: int = 1


class IngestionQueue:
    def __init__(self, redis_url: Optional[str], queue_name: str = "ingestion_queue") -> None:
        self.queue_name = queue_name
        self._redis = aioredis.from_url(redis_url) if redis_url else None
        self._memory_queue: asyncio.Queue[WorkItem] = asyncio.Queue()

    @property
    def enabled(self) -> bool:
        return True

    async def enqueue(self, item: WorkItem) -> None:
        if self._redis:
            payload = json.dumps(item.__dict__)
            await self._redis.rpush(self.queue_name, payload)
            return
        await self._memory_queue.put(item)

    async def pop(self, timeout: int = 5) -> Optional[WorkItem]:
        if self._redis:
            result = await self._redis.blpop(self.queue_name, timeout=timeout)
            if not result:
                return None
            _, payload = result
            decoded = payload.decode() if isinstance(payload, (bytes, bytearray)) else payload
            data: dict[str, Any] = json.loads(decoded)
            return WorkItem(**data)
        try:
            return await asyncio.wait_for(self._memory_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
