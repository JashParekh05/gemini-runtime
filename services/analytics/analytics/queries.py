"""ClickHouse query builders — parameterized, no raw f-string injection."""

from __future__ import annotations

from shared.db.clickhouse import execute_with_column_types


def get_session_trace(session_id: str) -> list[dict]:  # type: ignore[type-arg]
    rows, cols = execute_with_column_types(
        """
        SELECT event_id, agent_id, agent_role, event_type,
               sequence_number, emitted_at, server_received_at, payload
        FROM events
        WHERE session_id = %(session_id)s
        ORDER BY sequence_number ASC
        """,
        {"session_id": session_id},
    )
    col_names = [c[0] for c in cols]
    return [dict(zip(col_names, row)) for row in rows]


def get_session_cost(session_id: str) -> dict:  # type: ignore[type-arg]
    rows, _ = execute_with_column_types(
        """
        SELECT
            sum(cost_usd)                           AS total_cost_usd,
            sum(prompt_tokens + completion_tokens)  AS total_tokens,
            count()                                 AS total_tool_calls,
            countIf(status = 'failed')              AS failed_tool_calls
        FROM tool_call_metrics
        WHERE session_id = %(session_id)s
        """,
        {"session_id": session_id},
    )
    if not rows:
        return {}
    r = rows[0]
    return {
        "total_cost_usd": float(r[0] or 0),
        "total_tokens": int(r[1] or 0),
        "total_tool_calls": int(r[2] or 0),
        "failed_tool_calls": int(r[3] or 0),
    }


def get_session_latency(session_id: str) -> list[dict]:  # type: ignore[type-arg]
    rows, cols = execute_with_column_types(
        """
        SELECT
            tool_name,
            agent_role,
            quantile(0.50)(latency_ms) AS p50,
            quantile(0.95)(latency_ms) AS p95,
            quantile(0.99)(latency_ms) AS p99,
            count()                    AS total_calls,
            countIf(status = 'failed') AS failed_calls,
            avg(cost_usd)              AS avg_cost_usd
        FROM tool_call_metrics
        WHERE session_id = %(session_id)s
        GROUP BY tool_name, agent_role
        ORDER BY p95 DESC
        """,
        {"session_id": session_id},
    )
    col_names = [c[0] for c in cols]
    return [dict(zip(col_names, row)) for row in rows]


def get_global_tool_stats(hours: int = 24) -> list[dict]:  # type: ignore[type-arg]
    rows, cols = execute_with_column_types(
        """
        SELECT
            tool_name,
            agent_role,
            quantile(0.50)(latency_ms) AS p50,
            quantile(0.95)(latency_ms) AS p95,
            count()                    AS total_calls,
            countIf(status = 'failed') AS failed_calls,
            round(countIf(status = 'failed') / count() * 100, 2) AS error_rate_pct
        FROM tool_call_metrics
        WHERE started_at >= now() - INTERVAL %(hours)s HOUR
        GROUP BY tool_name, agent_role
        ORDER BY total_calls DESC
        LIMIT 50
        """,
        {"hours": hours},
    )
    col_names = [c[0] for c in cols]
    return [dict(zip(col_names, row)) for row in rows]


def get_recent_sessions(limit: int = 20) -> list[dict]:  # type: ignore[type-arg]
    rows, cols = execute_with_column_types(
        """
        SELECT
            session_id,
            min(emitted_at)            AS started_at,
            max(emitted_at)            AS ended_at,
            countIf(event_type = 'session_completed') AS completed,
            countIf(event_type = 'session_failed')    AS failed,
            count()                                    AS total_events
        FROM events
        GROUP BY session_id
        ORDER BY started_at DESC
        LIMIT %(limit)s
        """,
        {"limit": limit},
    )
    col_names = [c[0] for c in cols]
    return [dict(zip(col_names, row)) for row in rows]
