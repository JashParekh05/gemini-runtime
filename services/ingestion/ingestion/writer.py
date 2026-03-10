from __future__ import annotations

import logging
from typing import Any

from shared.db import clickhouse, postgres
from shared.models.events import (
    AnyEvent,
    EventType,
    ToolCallFinishedEvent,
    ToolCallFailedEvent,
    ToolCallStartedEvent,
)

logger = logging.getLogger(__name__)


class ClickHouseWriter:
    def write_batch(self, events: list[AnyEvent]) -> None:
        if not events:
            return

        event_rows: list[dict[str, Any]] = []
        metric_rows: list[dict[str, Any]] = []

        for ev in events:
            event_rows.append({
                "event_id": str(ev.event_id),
                "session_id": str(ev.session_id),
                "agent_id": ev.agent_id,
                "agent_role": ev.agent_role.value,
                "event_type": ev.event_type.value,
                "sequence_number": ev.sequence_number,
                "emitted_at": ev.emitted_at,
                "server_received_at": ev.server_received_at or ev.emitted_at,
                "payload": ev.model_dump_json(),
            })

            if isinstance(ev, ToolCallFinishedEvent):
                metric_rows.append({
                    "session_id": str(ev.session_id),
                    "agent_id": ev.agent_id,
                    "agent_role": ev.agent_role.value,
                    "tool_name": ev.tool_name,
                    "started_at": ev.emitted_at,
                    "latency_ms": ev.latency_ms,
                    "prompt_tokens": 0,
                    "completion_tokens": ev.completion_tokens or 0,
                    "cost_usd": ev.cost_usd or 0.0,
                    "status": "completed",
                })
            elif isinstance(ev, ToolCallFailedEvent):
                metric_rows.append({
                    "session_id": str(ev.session_id),
                    "agent_id": ev.agent_id,
                    "agent_role": ev.agent_role.value,
                    "tool_name": ev.tool_name,
                    "started_at": ev.emitted_at,
                    "latency_ms": 0.0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost_usd": 0.0,
                    "status": "failed",
                })

        event_cols = ["event_id", "session_id", "agent_id", "agent_role", "event_type",
                      "sequence_number", "emitted_at", "server_received_at", "payload"]
        metric_cols = ["session_id", "agent_id", "agent_role", "tool_name", "started_at",
                       "latency_ms", "prompt_tokens", "completion_tokens", "cost_usd", "status"]

        try:
            clickhouse.insert("events", event_rows, event_cols)
            if metric_rows:
                clickhouse.insert("tool_call_metrics", metric_rows, metric_cols)
        except Exception:
            logger.exception("ClickHouse write failed")
            raise


class PostgresWriter:
    """Mirrors tool invocations into Postgres for FK-based queries."""

    async def upsert_batch(self, events: list[AnyEvent]) -> None:
        from sqlalchemy import text

        tool_starts: dict[str, ToolCallStartedEvent] = {}
        results: list[dict[str, Any]] = []

        for ev in events:
            if isinstance(ev, ToolCallStartedEvent):
                tool_starts[str(ev.tool_call_id)] = ev
            elif isinstance(ev, (ToolCallFinishedEvent, ToolCallFailedEvent)):
                row = {
                    "invocation_id": str(ev.tool_call_id),
                    "session_id": str(ev.session_id),
                    "agent_id": ev.agent_id,
                    "tool_name": ev.tool_name,
                    "args": "{}",
                    "started_at": ev.emitted_at,
                    "finished_at": ev.emitted_at,
                    "status": "completed" if isinstance(ev, ToolCallFinishedEvent) else "failed",
                }
                if isinstance(ev, ToolCallFinishedEvent):
                    row["latency_ms"] = ev.latency_ms
                    row["completion_tokens"] = ev.completion_tokens or 0
                    row["cost_usd"] = ev.cost_usd or 0.0
                    row["error"] = None
                else:
                    row["error"] = ev.error_message
                results.append(row)

        if not results:
            return

        factory = postgres.get_session_factory()
        async with factory() as session:
            for row in results:
                await session.execute(
                    text("""
                        INSERT INTO tool_invocations
                            (invocation_id, session_id, agent_id, tool_name, args,
                             started_at, finished_at, latency_ms, completion_tokens,
                             cost_usd, error, status)
                        VALUES
                            (:invocation_id, :session_id, :agent_id, :tool_name, :args::jsonb,
                             :started_at, :finished_at, :latency_ms, :completion_tokens,
                             :cost_usd, :error, :status)
                        ON CONFLICT (invocation_id) DO UPDATE SET
                            finished_at = EXCLUDED.finished_at,
                            latency_ms = EXCLUDED.latency_ms,
                            status = EXCLUDED.status,
                            error = EXCLUDED.error
                    """),
                    {
                        "latency_ms": row.get("latency_ms"),
                        "completion_tokens": row.get("completion_tokens", 0),
                        "cost_usd": row.get("cost_usd", 0.0),
                        **row,
                    },
                )
            await session.commit()
