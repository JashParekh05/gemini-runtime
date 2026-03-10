from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from services.ingestion.ingestion.validator import EventValidator
from services.ingestion.ingestion.writer import ClickHouseWriter, PostgresWriter

router = APIRouter(prefix="/events", tags=["events"])
logger = logging.getLogger(__name__)

_validator = EventValidator()
_ch_writer = ClickHouseWriter()
_pg_writer = PostgresWriter()


@router.post("", status_code=202)
async def ingest_event(payload: dict[str, Any]) -> dict[str, str]:
    """HTTP fallback endpoint — accepts a single event as JSON."""
    try:
        event = _validator.validate(payload)
        await asyncio.gather(
            asyncio.to_thread(_ch_writer.write_batch, [event]),
            _pg_writer.upsert_batch([event]),
        )
        return {"status": "accepted", "event_id": str(event.event_id)}
    except Exception as exc:
        logger.exception("Event ingestion failed")
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/batch", status_code=202)
async def ingest_batch(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    """Ingest multiple events in one request."""
    events = []
    errors = []
    for i, p in enumerate(payloads):
        try:
            events.append(_validator.validate(p))
        except Exception as exc:
            errors.append({"index": i, "error": str(exc)})

    if events:
        await asyncio.gather(
            asyncio.to_thread(_ch_writer.write_batch, events),
            _pg_writer.upsert_batch(events),
        )

    return {
        "accepted": len(events),
        "rejected": len(errors),
        "errors": errors,
    }
