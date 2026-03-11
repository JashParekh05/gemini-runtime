"""
NDJSONStreamParser — parses gemini-cli --output-format stream-json stdout.

Each line from gemini-cli is one of:
  {"type": "tool_call",    "id": "...", "name": "...", "args": {...}}
  {"type": "tool_result",  "id": "...", "output": "...", "latency_ms": 312, "error": null}
  {"type": "thinking",     "content": "..."}
  {"type": "final_response", "content": "..."}
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from shared.models.events import (
    AgentRole,
    ToolCallFailedEvent,
    ToolCallFinishedEvent,
    ToolCallStartedEvent,
)
from shared.telemetry.cost import estimate_cost
from shared.telemetry.otel import get_tracer
from services.agent_worker.agent_worker.event_emitter import EventEmitter

logger = logging.getLogger(__name__)
tracer = get_tracer("agent_worker")


@dataclass
class PendingCall:
    tool_name: str
    tool_args: dict[str, Any]
    started_at: float = field(default_factory=time.monotonic)
    span: Any = None


@dataclass
class ParseResult:
    final_content: str = ""
    total_tokens: int = 0
    tool_call_count: int = 0


class NDJSONStreamParser:
    def __init__(
        self,
        session_id: uuid.UUID,
        agent_id: str,
        agent_role: AgentRole,
        emitter: EventEmitter,
        model: str = "gemini-2.5-pro",
    ) -> None:
        self._session_id = session_id
        self._agent_id = agent_id
        self._agent_role = agent_role
        self._emitter = emitter
        self._model = model
        self._pending: dict[str, PendingCall] = {}
        self.result = ParseResult()

    async def feed_line(self, line: str) -> bool:
        """Process one NDJSON line. Returns True when final_response is seen."""
        line = line.strip()
        if not line:
            return False
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            logger.debug("Non-JSON line from gemini-cli: %s", line[:120])
            return False

        match obj.get("type"):
            case "tool_call":
                await self._on_tool_call(obj)
            case "tool_result":
                await self._on_tool_result(obj)
            case "final_response":
                self.result.final_content = obj.get("content", "")
                self.result.total_tokens = obj.get("total_tokens", 0)
                return True
            case "thinking":
                pass  # not actionable, skip
            case _:
                logger.debug("Unknown gemini-cli event type: %s", obj.get("type"))

        return False

    async def _on_tool_call(self, obj: dict[str, Any]) -> None:
        call_id = obj.get("id", str(uuid.uuid4()))
        tool_name = obj.get("name", "unknown")
        tool_args = obj.get("args", {})

        span = tracer.start_span(
            f"tool_call/{tool_name}",
            attributes={
                "agent.role": self._agent_role.value,
                "tool.name": tool_name,
                "session.id": str(self._session_id),
            },
        )

        self._pending[call_id] = PendingCall(
            tool_name=tool_name,
            tool_args=tool_args,
            span=span,
        )
        self.result.tool_call_count += 1

        await self._emitter.emit(
            ToolCallStartedEvent(
                session_id=self._session_id,
                agent_id=self._agent_id,
                agent_role=self._agent_role,
                tool_call_id=uuid.UUID(call_id) if len(call_id) == 36 else uuid.uuid4(),
                tool_name=tool_name,
                tool_args=tool_args,
            )
        )

    async def _on_tool_result(self, obj: dict[str, Any]) -> None:
        call_id = obj.get("id", "")
        pending = self._pending.pop(call_id, None)
        if pending is None:
            logger.warning("Received tool_result for unknown call_id %s", call_id)
            return

        latency_ms = obj.get("latency_ms") or (time.monotonic() - pending.started_at) * 1000
        error = obj.get("error")
        tokens_in = obj.get("tokens_in", 0)
        tokens_out = obj.get("tokens_out", 0)
        cost = estimate_cost(self._model, tokens_in, tokens_out)

        if pending.span:
            pending.span.set_attribute("latency_ms", latency_ms)
            pending.span.set_attribute("cost_usd", cost)
            pending.span.end()

        tool_call_uuid = uuid.UUID(call_id) if len(call_id) == 36 else uuid.uuid4()

        if error:
            await self._emitter.emit(
                ToolCallFailedEvent(
                    session_id=self._session_id,
                    agent_id=self._agent_id,
                    agent_role=self._agent_role,
                    tool_call_id=tool_call_uuid,
                    tool_name=pending.tool_name,
                    error_type="tool_error",
                    error_message=str(error),
                )
            )
        else:
            await self._emitter.emit(
                ToolCallFinishedEvent(
                    session_id=self._session_id,
                    agent_id=self._agent_id,
                    agent_role=self._agent_role,
                    tool_call_id=tool_call_uuid,
                    tool_name=pending.tool_name,
                    completion_tokens=tokens_out,
                    latency_ms=latency_ms,
                    cost_usd=cost,
                )
            )
