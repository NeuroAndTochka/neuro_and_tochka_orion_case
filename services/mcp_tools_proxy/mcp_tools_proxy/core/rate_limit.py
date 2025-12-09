from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, status


class ToolRateLimiter:
    def __init__(self, max_calls: int, max_tokens: int) -> None:
        self.max_calls = max_calls
        self.max_tokens = max_tokens
        self._calls: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, 0.0))
        self._lock = asyncio.Lock()

    async def check(self, key: str, estimated_tokens: int) -> None:
        async with self._lock:
            count, tokens = self._calls[key]
            if count + 1 > self.max_calls or tokens + estimated_tokens > self.max_tokens:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={"code": "RATE_LIMIT_EXCEEDED", "count": count, "tokens": tokens},
                )
            self._calls[key] = (count + 1, tokens + estimated_tokens)

    async def reset(self, key: str) -> None:
        async with self._lock:
            if key in self._calls:
                del self._calls[key]
