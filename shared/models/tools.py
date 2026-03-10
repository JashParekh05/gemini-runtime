from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class InvocationStatus(StrEnum):
    running = "running"
    completed = "completed"
    failed = "failed"


class ToolInvocation(BaseModel):
    invocation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    agent_id: str
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    status: InvocationStatus = InvocationStatus.running
