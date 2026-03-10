from __future__ import annotations

import redis.asyncio as aioredis

from shared.config import settings

_client: aioredis.Redis | None = None  # type: ignore[type-arg]


def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
