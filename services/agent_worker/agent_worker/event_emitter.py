"""Publishes observability events to stream:events."""

from __future__ import annotations

import logging

from shared.db.redis_client import get_redis
from shared.messaging.streams import STREAM_EVENTS, StreamProducer
from shared.models.events import AnyEvent

logger = logging.getLogger(__name__)


class EventEmitter:
    def __init__(self) -> None:
        self._producer: StreamProducer | None = None

    def _get_producer(self) -> StreamProducer:
        if self._producer is None:
            self._producer = StreamProducer(get_redis())
        return self._producer

    async def emit(self, event: AnyEvent) -> None:
        try:
            producer = self._get_producer()
            await producer.publish_raw(
                STREAM_EVENTS,
                "Event",
                event.model_dump(mode="json"),
            )
        except Exception:
            logger.exception("Failed to emit event %s", event.event_type)
