from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from shared.models.events import AgentRole


class SessionStatus(StrEnum):
    pending = "pending"
    planning = "planning"
    researching = "researching"
    executing = "executing"
    verifying = "verifying"
    completed = "completed"
    failed = "failed"


class AgentStatus(StrEnum):
    idle = "idle"
    busy = "busy"
    waiting = "waiting"
    error = "error"


class Session(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.pending
    task_description: str
    task_graph_id: uuid.UUID | None = None
    initiator: str = "api"
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    agent_id: str
    role: AgentRole
    session_id: uuid.UUID
    current_task_id: uuid.UUID | None = None
    status: AgentStatus = AgentStatus.idle
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    process_pid: int | None = None
    retry_count: int = 0
    context_window_tokens: int = 0
