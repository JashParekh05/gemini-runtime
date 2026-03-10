"""Redis Streams producer and consumer base classes."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import redis.asyncio as aioredis

from shared.messaging.schemas import StreamMessage

logger = logging.getLogger(__name__)

# Stream names
STREAM_EVENTS = "stream:events"
STREAM_RESULTS = "stream:results"
STREAM_HEARTBEATS = "stream:heartbeats"

TASK_STREAM = {
    "planner": "stream:tasks:planner",
    "researcher": "stream:tasks:researcher",
    "executor": "stream:tasks:executor",
    "verifier": "stream:tasks:verifier",
}


class StreamProducer:
    def __init__(self, redis: aioredis.Redis) -> None:  # type: ignore[type-arg]
        self._r = redis

    async def publish(self, stream: str, message: StreamMessage) -> str:
        """Append message to stream, return Redis message ID."""
        data = {
            "schema_version": message.schema_version,
            "payload_type": message.payload_type,
            "payload": json.dumps(message.payload),
            "trace_id": message.trace_id,
            "produced_at": message.produced_at.isoformat(),
        }
        msg_id: str = await self._r.xadd(stream, data)
        return msg_id

    async def publish_raw(self, stream: str, payload_type: str, payload: dict[str, Any]) -> str:
        msg = StreamMessage(payload_type=payload_type, payload=payload)
        return await self.publish(stream, msg)


class StreamConsumer:
    """
    Redis Streams consumer group wrapper.

    - Creates the consumer group if it doesn't exist.
    - Reads in batches, calls `handler` for each message.
    - XACKs only after handler completes (at-least-once delivery).
    - Reclaims stale PEL entries after `claim_after_ms`.
    """

    def __init__(
        self,
        redis: aioredis.Redis,  # type: ignore[type-arg]
        stream: str,
        group: str,
        consumer_name: str,
        batch_size: int = 50,
        block_ms: int = 1000,
        claim_after_ms: int = 30_000,
    ) -> None:
        self._r = redis
        self.stream = stream
        self.group = group
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.claim_after_ms = claim_after_ms
        self._stop = asyncio.Event()

    async def ensure_group(self) -> None:
        try:
            await self._r.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def consume(
        self,
        handler: Callable[[str, StreamMessage], Awaitable[None]],
    ) -> None:
        await self.ensure_group()
        while not self._stop.is_set():
            try:
                await self._process_pending(handler)
                await self._process_new(handler)
            except Exception:
                logger.exception("Consumer error on stream %s", self.stream)
                await asyncio.sleep(1)

    async def _process_new(
        self,
        handler: Callable[[str, StreamMessage], Awaitable[None]],
    ) -> None:
        results = await self._r.xreadgroup(
            self.group,
            self.consumer_name,
            {self.stream: ">"},
            count=self.batch_size,
            block=self.block_ms,
        )
        if not results:
            return
        for _stream, messages in results:
            for msg_id, fields in messages:
                await self._handle(msg_id, fields, handler)

    async def _process_pending(
        self,
        handler: Callable[[str, StreamMessage], Awaitable[None]],
    ) -> None:
        """Reclaim messages stuck in PEL."""
        claimed = await self._r.xautoclaim(
            self.stream,
            self.group,
            self.consumer_name,
            min_idle_time=self.claim_after_ms,
            start_id="0-0",
            count=self.batch_size,
        )
        # xautoclaim returns (next_id, messages, deleted_ids)
        messages = claimed[1] if isinstance(claimed, (list, tuple)) and len(claimed) > 1 else []
        for msg_id, fields in messages:
            await self._handle(msg_id, fields, handler)

    async def _handle(
        self,
        msg_id: str,
        fields: dict[str, str],
        handler: Callable[[str, StreamMessage], Awaitable[None]],
    ) -> None:
        try:
            msg = StreamMessage(
                schema_version=fields.get("schema_version", "1.0"),
                payload_type=fields["payload_type"],
                payload=json.loads(fields["payload"]),
                trace_id=fields.get("trace_id", ""),
                produced_at=datetime.fromisoformat(fields.get("produced_at", datetime.utcnow().isoformat())),
            )
            await handler(msg_id, msg)
            await self._r.xack(self.stream, self.group, msg_id)
        except Exception:
            logger.exception("Failed to process message %s", msg_id)

    def stop(self) -> None:
        self._stop.set()
