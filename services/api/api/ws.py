"""WebSocket endpoint for live session event streaming."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from shared.db.redis_client import get_redis
from shared.messaging.streams import STREAM_EVENTS

logger = logging.getLogger(__name__)


async def session_event_stream(websocket: WebSocket, session_id: str, replay: bool = False) -> None:
    """
    Stream events for a session over WebSocket.
    - replay=True: read from the beginning (id="0")
    - replay=False: tail live events (id="$")
    """
    await websocket.accept()
    redis = get_redis()
    last_id = "0" if replay else "$"

    try:
        while True:
            messages = await redis.xread({STREAM_EVENTS: last_id}, count=50, block=500)
            for _stream, msgs in (messages or []):
                for msg_id, fields in msgs:
                    last_id = msg_id
                    try:
                        payload = json.loads(fields.get("payload", "{}"))
                        if payload.get("session_id") == session_id:
                            await websocket.send_json(payload)
                    except Exception:
                        pass
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session %s", session_id)
    except Exception:
        logger.exception("WebSocket error for session %s", session_id)
        await websocket.close()
