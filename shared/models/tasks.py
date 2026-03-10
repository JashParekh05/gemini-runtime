from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from shared.models.events import AgentRole


class TaskStatus(StrEnum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class TaskType(StrEnum):
    plan = "plan"
    research = "research"
    implement = "implement"
    verify = "verify"


class TaskNode(BaseModel):
    task_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_type: TaskType
    agent_role: AgentRole
    description: str
    dependencies: list[uuid.UUID] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    status: TaskStatus = TaskStatus.pending
    assigned_agent_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0
    max_retries: int = 3


class TaskGraph(BaseModel):
    graph_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    nodes: list[TaskNode] = Field(default_factory=list)
    # adjacency[task_id] = list of task_ids that depend on it
    adjacency: dict[str, list[str]] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.pending

    def get_node(self, task_id: uuid.UUID) -> TaskNode | None:
        return next((n for n in self.nodes if n.task_id == task_id), None)

    def is_complete(self) -> bool:
        return all(n.status == TaskStatus.completed for n in self.nodes)

    def has_failures(self) -> bool:
        return any(n.status == TaskStatus.failed for n in self.nodes)


class TaskResult(BaseModel):
    task_id: uuid.UUID
    session_id: uuid.UUID
    agent_id: str
    status: TaskStatus
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
