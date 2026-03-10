from __future__ import annotations

from datetime import datetime
from typing import Any

from shared.models.events import AnyEvent, parse_event


class EventValidator:
    """Validates and enriches raw event dicts."""

    @staticmethod
    def validate(data: dict[str, Any]) -> AnyEvent:
        event = parse_event(data)
        # Use model_copy since events are frozen
        return event.model_copy(update={"server_received_at": datetime.utcnow()})
