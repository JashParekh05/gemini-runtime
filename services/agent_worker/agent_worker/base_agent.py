"""BaseAgent ABC — all role agents inherit from this."""

from __future__ import annotations

import abc
import uuid
from typing import Any

from shared.models.events import AgentRole
from shared.models.tasks import TaskResult, TaskStatus
from services.agent_worker.agent_worker.event_emitter import EventEmitter
from services.agent_worker.agent_worker.gemini_runner import GeminiRunner


class BaseAgent(abc.ABC):
    role: AgentRole

    def __init__(self, session_id: uuid.UUID) -> None:
        self._session_id = session_id
        self._agent_id = f"{self.role.value}-{str(session_id)[:8]}"
        self._emitter = EventEmitter()
        self._runner = GeminiRunner(
            session_id=session_id,
            agent_id=self._agent_id,
            agent_role=self.role,
            emitter=self._emitter,
            mcp_server_path=self._mcp_server_path(),
        )

    def _mcp_server_path(self) -> str | None:
        """Override to point to this role's MCP server dist directory."""
        return None

    @abc.abstractmethod
    def build_prompt(self, task_description: str, inputs: dict[str, Any]) -> str:
        """Construct the full prompt string for gemini-cli."""

    @abc.abstractmethod
    def parse_output(self, content: str) -> dict[str, Any]:
        """Parse gemini-cli final_response content into structured outputs."""

    async def run(
        self,
        task_id: uuid.UUID,
        task_description: str,
        inputs: dict[str, Any],
    ) -> TaskResult:
        prompt = self.build_prompt(task_description, inputs)
        try:
            result = await self._runner.run(prompt)
            outputs = self.parse_output(result.content)
            return TaskResult(
                task_id=task_id,
                session_id=self._session_id,
                agent_id=self._agent_id,
                status=TaskStatus.completed,
                outputs=outputs,
                total_tokens=result.total_tokens,
            )
        except Exception as exc:
            return TaskResult(
                task_id=task_id,
                session_id=self._session_id,
                agent_id=self._agent_id,
                status=TaskStatus.failed,
                error=str(exc),
            )
