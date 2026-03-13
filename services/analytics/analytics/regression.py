"""Regression detector — compares two sessions on cost, latency, and error rate."""

from __future__ import annotations

from dataclasses import dataclass

from services.analytics.analytics.queries import get_session_cost, get_session_latency


@dataclass
class MetricDelta:
    metric: str
    baseline: float
    target: float
    delta_pct: float
    is_regression: bool


@dataclass
class RegressionReport:
    baseline_session_id: str
    target_session_id: str
    deltas: list[MetricDelta]
    has_regression: bool
    summary: str


class RegressionDetector:
    def __init__(self, threshold_pct: float = 20.0) -> None:
        self.threshold_pct = threshold_pct

    def compare(self, baseline_id: str, target_id: str) -> RegressionReport:
        baseline_cost = get_session_cost(baseline_id)
        target_cost = get_session_cost(target_id)

        baseline_latency = self._max_p95(get_session_latency(baseline_id))
        target_latency = self._max_p95(get_session_latency(target_id))

        deltas = []

        for metric, b_val, t_val, higher_is_worse in [
            ("total_cost_usd", baseline_cost.get("total_cost_usd", 0), target_cost.get("total_cost_usd", 0), True),
            ("p95_latency_ms", baseline_latency, target_latency, True),
            ("error_rate", self._error_rate(baseline_cost), self._error_rate(target_cost), True),
            ("total_tokens", baseline_cost.get("total_tokens", 0), target_cost.get("total_tokens", 0), True),
        ]:
            if b_val == 0:
                delta_pct = 0.0
            else:
                delta_pct = (t_val - b_val) / b_val * 100

            is_regression = higher_is_worse and delta_pct > self.threshold_pct
            deltas.append(MetricDelta(
                metric=metric,
                baseline=b_val,
                target=t_val,
                delta_pct=round(delta_pct, 2),
                is_regression=is_regression,
            ))

        has_regression = any(d.is_regression for d in deltas)
        regressions = [d.metric for d in deltas if d.is_regression]
        summary = (
            f"Regression detected in: {', '.join(regressions)}"
            if has_regression
            else "No regressions detected"
        )

        return RegressionReport(
            baseline_session_id=baseline_id,
            target_session_id=target_id,
            deltas=deltas,
            has_regression=has_regression,
            summary=summary,
        )

    @staticmethod
    def _max_p95(latency_rows: list[dict]) -> float:  # type: ignore[type-arg]
        if not latency_rows:
            return 0.0
        return max(float(r.get("p95", 0)) for r in latency_rows)

    @staticmethod
    def _error_rate(cost_data: dict) -> float:  # type: ignore[type-arg]
        total = cost_data.get("total_tool_calls", 0)
        failed = cost_data.get("failed_tool_calls", 0)
        return (failed / total * 100) if total > 0 else 0.0
