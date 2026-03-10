"""Redis Stream consumer for the ingestion service."""

from __future__ import annotations

import asyncio
import logging

from shared.db.redis_client import get_redis
from shared.messaging.streams import STREAM_EVENTS, StreamConsumer, StreamMessage
from services.ingestion.ingestion.validator import EventValidator
from services.ingestion.ingestion.writer import ClickHouseWriter, PostgresWriter

logger = logging.getLogger(__name__)

_validator = EventValidator()
_ch_writer = ClickHouseWriter()
_pg_writer = PostgresWriter()


async def handle_batch(msg_id: str, message: StreamMessage) -> None:
    """Process a single event message from the stream."""
    try:
        event = _validator.validate(message.payload)
        # Write to both stores concurrently
        await asyncio.gather(
            asyncio.to_thread(_ch_writer.write_batch, [event]),
            _pg_writer.upsert_batch([event]),
        )
    except Exception:
        logger.exception("Failed to process event message %s", msg_id)
        raise  # Re-raise so XACK is skipped (at-least-once delivery)


async def start_consumer() -> None:
    redis = get_redis()
    consumer = StreamConsumer(
        redis=redis,
        stream=STREAM_EVENTS,
        group="cg:ingestion",
        consumer_name="ingestion-worker-1",
        batch_size=100,
    )
    logger.info("Starting event stream consumer on %s", STREAM_EVENTS)
    await consumer.consume(handle_batch)
