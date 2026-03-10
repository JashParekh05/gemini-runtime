"""Append-only event schema. All events are immutable once written."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Union

from pydantic import BaseModel, ConfigDict, Field


class AgentRole(StrEnum):
    planner = "planner"
    researcher = "researcher"
    executor = "executor"
    verifier = "verifier"


class EventType(StrEnum):
    session_started = "session_started"
    tool_call_started = "tool_call_started"
    tool_call_finished = "tool_call_finished"
    tool_call_failed = "tool_call_failed"
    agent_retry = "agent_retry"
    agent_handoff = "agent_handoff"
    session_completed = "session_completed"
    session_failed = "session_failed"


class _BaseEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    agent_id: str
    agent_role: AgentRole
    sequence_number: int = 0
    emitted_at: datetime = Field(default_factory=datetime.utcnow)
    server_received_at: datetime | None = None


# ── per-type payloads ──────────────────────────────────────────────────────────

class SessionStartedEvent(_BaseEvent):
    event_type: EventType = Field(EventType.session_started, frozen=True)
    task_description: str
    task_graph_id: uuid.UUID | None = None
    initiator: str = "api"


class ToolCallStartedEvent(_BaseEvent):
    event_type: EventType = Field(EventType.tool_call_started, frozen=True)
    tool_call_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    prompt_tokens: int | None = None


class ToolCallFinishedEvent(_BaseEvent):
    event_type: EventType = Field(EventType.tool_call_finished, frozen=True)
    tool_call_id: uuid.UUID
    tool_name: str
    output_summary: str = ""
    completion_tokens: int | None = None
    latency_ms: float
    cost_usd: float | None = None


class ToolCallFailedEvent(_BaseEvent):
    event_type: EventType = Field(EventType.tool_call_failed, frozen=True)
    tool_call_id: uuid.UUID
    tool_name: str
    error_type: str
    error_message: str
    retry_count: int = 0


class AgentRetryEvent(_BaseEvent):
    event_type: EventType = Field(EventType.agent_retry, frozen=True)
    reason: str
    retry_number: int
    max_retries: int


class AgentHandoffEvent(_BaseEvent):
    event_type: EventType = Field(EventType.agent_handoff, frozen=True)
    from_role: AgentRole
    to_role: AgentRole
    artifact_ref: str | None = None


class SessionCompletedEvent(_BaseEvent):
    event_type: EventType = Field(EventType.session_completed, frozen=True)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0


class SessionFailedEvent(_BaseEvent):
    event_type: EventType = Field(EventType.session_failed, frozen=True)
    failure_reason: str
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0


# ── discriminated union ────────────────────────────────────────────────────────

AnyEvent = Annotated[
    Union[
        SessionStartedEvent,
        ToolCallStartedEvent,
        ToolCallFinishedEvent,
        ToolCallFailedEvent,
        AgentRetryEvent,
        AgentHandoffEvent,
        SessionCompletedEvent,
        SessionFailedEvent,
    ],
    Field(discriminator="event_type"),
]


def parse_event(data: dict[str, Any]) -> AnyEvent:
    """Deserialize a dict into the correct event type."""
    from pydantic import TypeAdapter

    adapter: TypeAdapter[AnyEvent] = TypeAdapter(AnyEvent)
    return adapter.validate_python(data)
