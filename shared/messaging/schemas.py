from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StreamMessage(BaseModel):
    """Envelope for all Redis Stream messages."""

    schema_version: str = "1.0"
    payload_type: str  # e.g. "TaskDispatch", "TaskResult", "Event"
    payload: dict[str, Any]
    trace_id: str = ""
    produced_at: datetime = Field(default_factory=datetime.utcnow)


class TaskDispatch(BaseModel):
    """Sent by orchestrator → agent task stream."""

    session_id: str
    task_id: str
    task_type: str
    agent_role: str
    description: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0


class TaskResult(BaseModel):
    """Sent by agent worker → results stream."""

    session_id: str
    task_id: str
    agent_id: str
    status: str  # completed | failed
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


class Heartbeat(BaseModel):
    """Agent liveness signal."""

    agent_id: str
    agent_role: str
    session_id: str | None = None
    current_task_id: str | None = None
    status: str = "idle"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
