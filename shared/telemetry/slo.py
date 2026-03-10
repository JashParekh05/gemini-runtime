"""SLO/SLI definitions per agent role."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SLOStatus(StrEnum):
    healthy = "healthy"
    at_risk = "at_risk"
    breached = "breached"


@dataclass
class SLODefinition:
    name: str
    description: str
    target: float          # 0.0 – 1.0
    window_hours: int = 24


@dataclass
class SLOResult:
    slo: SLODefinition
    current_rate: float
    total_events: int
    good_events: int
    status: SLOStatus = field(init=False)
    error_budget_remaining: float = field(init=False)

    def __post_init__(self) -> None:
        self.error_budget_remaining = max(
            0.0, (self.current_rate - (1.0 - self.slo.target)) / self.slo.target
        )
        if self.current_rate >= self.slo.target:
            self.status = SLOStatus.healthy
        elif self.current_rate >= self.slo.target * 0.95:
            self.status = SLOStatus.at_risk
        else:
            self.status = SLOStatus.breached


# ── SLO catalogue ──────────────────────────────────────────────────────────────

SLOS: dict[str, SLODefinition] = {
    "planner_latency": SLODefinition(
        name="planner_latency",
        description="95% of planning tasks complete in < 30s",
        target=0.95,
    ),
    "executor_first_pass": SLODefinition(
        name="executor_first_pass",
        description="90% of executor tasks pass verifier on first attempt",
        target=0.90,
    ),
    "verifier_parse_success": SLODefinition(
        name="verifier_parse_success",
        description="99% of verifier calls return a structured verdict",
        target=0.99,
    ),
    "system_completion": SLODefinition(
        name="system_completion",
        description="95% of sessions complete successfully end-to-end",
        target=0.95,
    ),
}
