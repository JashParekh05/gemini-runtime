"""Evaluates SLO compliance from ClickHouse data."""

from __future__ import annotations

from shared.db.clickhouse import execute_with_column_types
from shared.telemetry.slo import SLOS, SLOResult


def evaluate_all_slos(window_hours: int = 24) -> dict[str, SLOResult]:
    results = {}

    # planner_latency: % of planner tasks with latency < 30s
    rows, _ = execute_with_column_types(
        """
        SELECT
            count()                                                    AS total,
            countIf(latency_ms < 30000 AND agent_role = 'planner')    AS good
        FROM tool_call_metrics
        WHERE started_at >= now() - INTERVAL %(hours)s HOUR
          AND agent_role = 'planner'
        """,
        {"hours": window_hours},
    )
    total, good = (int(rows[0][0]), int(rows[0][1])) if rows else (0, 0)
    results["planner_latency"] = SLOResult(
        slo=SLOS["planner_latency"],
        current_rate=good / total if total > 0 else 1.0,
        total_events=total,
        good_events=good,
    )

    # verifier_parse_success: % of verifier sessions where verdict was not a parse failure
    rows, _ = execute_with_column_types(
        """
        SELECT
            count()                                           AS total,
            countIf(status = 'completed')                    AS good
        FROM tool_call_metrics
        WHERE started_at >= now() - INTERVAL %(hours)s HOUR
          AND agent_role = 'verifier'
        """,
        {"hours": window_hours},
    )
    total, good = (int(rows[0][0]), int(rows[0][1])) if rows else (0, 0)
    results["verifier_parse_success"] = SLOResult(
        slo=SLOS["verifier_parse_success"],
        current_rate=good / total if total > 0 else 1.0,
        total_events=total,
        good_events=good,
    )

    # system_completion: % of sessions that ended with session_completed
    rows, _ = execute_with_column_types(
        """
        SELECT
            count()                                                     AS total,
            countIf(event_type = 'session_completed')                   AS completed
        FROM (
            SELECT session_id,
                   argMax(event_type, sequence_number) AS event_type
            FROM events
            WHERE emitted_at >= now() - INTERVAL %(hours)s HOUR
              AND event_type IN ('session_completed', 'session_failed')
            GROUP BY session_id
        )
        """,
        {"hours": window_hours},
    )
    total, good = (int(rows[0][0]), int(rows[0][1])) if rows else (0, 0)
    results["system_completion"] = SLOResult(
        slo=SLOS["system_completion"],
        current_rate=good / total if total > 0 else 1.0,
        total_events=total,
        good_events=good,
    )

    return results
