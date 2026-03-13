from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query

from services.analytics.analytics.queries import (
    get_global_tool_stats,
    get_recent_sessions,
    get_session_cost,
    get_session_latency,
    get_session_trace,
)
from services.analytics.analytics.regression import RegressionDetector
from services.analytics.analytics.slo_evaluator import evaluate_all_slos

router = APIRouter(prefix="/analytics", tags=["analytics"])
_detector = RegressionDetector()


@router.get("/sessions/{session_id}/trace")
async def session_trace(session_id: str) -> list[dict]:  # type: ignore[type-arg]
    return get_session_trace(session_id)


@router.get("/sessions/{session_id}/cost")
async def session_cost(session_id: str) -> dict:  # type: ignore[type-arg]
    return get_session_cost(session_id)


@router.get("/sessions/{session_id}/latency")
async def session_latency(session_id: str) -> list[dict]:  # type: ignore[type-arg]
    return get_session_latency(session_id)


@router.get("/tools")
async def tool_stats(hours: int = Query(default=24, ge=1, le=168)) -> list[dict]:  # type: ignore[type-arg]
    return get_global_tool_stats(hours=hours)


@router.get("/sessions")
async def recent_sessions(limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:  # type: ignore[type-arg]
    return get_recent_sessions(limit=limit)


@router.get("/regression")
async def regression(
    baseline: str = Query(..., description="Baseline session ID"),
    target: str = Query(..., description="Target session ID to compare"),
    threshold: float = Query(default=20.0, description="Regression threshold %"),
) -> dict:  # type: ignore[type-arg]
    detector = RegressionDetector(threshold_pct=threshold)
    report = detector.compare(baseline, target)
    return {
        "baseline_session_id": report.baseline_session_id,
        "target_session_id": report.target_session_id,
        "has_regression": report.has_regression,
        "summary": report.summary,
        "deltas": [asdict(d) for d in report.deltas],
    }


@router.get("/slo")
async def slo_status(hours: int = Query(default=24, ge=1, le=168)) -> dict:  # type: ignore[type-arg]
    results = evaluate_all_slos(window_hours=hours)
    return {
        name: {
            "slo_name": r.slo.name,
            "description": r.slo.description,
            "target": r.slo.target,
            "current_rate": round(r.current_rate, 4),
            "status": r.status.value,
            "error_budget_remaining": round(r.error_budget_remaining, 4),
            "total_events": r.total_events,
            "good_events": r.good_events,
        }
        for name, r in results.items()
    }
