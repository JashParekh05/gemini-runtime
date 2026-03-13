#!/usr/bin/env python3
"""
Seed a complete fake session for dashboard demo purposes.
Run: python scripts/seed_demo.py
"""

import asyncio
import random
import uuid
from datetime import datetime, timedelta

import httpx

INGESTION_URL = "http://localhost:8002/events"

SESSION_ID = str(uuid.uuid4())
AGENT_IDS = {
    "planner": f"planner-{SESSION_ID[:8]}",
    "researcher": f"researcher-{SESSION_ID[:8]}",
    "executor": f"executor-{SESSION_ID[:8]}",
    "verifier": f"verifier-{SESSION_ID[:8]}",
}

TOOL_CALLS = [
    ("planner", "inspect_project_structure", 120, 0.0001),
    ("planner", "check_existing_tests", 80, 0.00005),
    ("researcher", "search_codebase", 450, 0.0003),
    ("researcher", "read_workspace_file", 310, 0.0002),
    ("researcher", "read_workspace_file", 280, 0.00018),
    ("researcher", "get_git_history", 90, 0.00006),
    ("executor", "write_file", 520, 0.0004),
    ("executor", "apply_unified_diff", 380, 0.00025),
    ("executor", "run_shell_command", 2100, 0.0015),
    ("verifier", "run_pytest", 4200, 0.003),
    ("verifier", "run_mypy", 1800, 0.0012),
    ("verifier", "run_ruff", 320, 0.0002),
]


def make_event(event_type: str, agent_role: str, seq: int, **kwargs) -> dict:
    base = {
        "event_type": event_type,
        "session_id": SESSION_ID,
        "agent_id": AGENT_IDS[agent_role],
        "agent_role": agent_role,
        "sequence_number": seq,
        "emitted_at": (datetime.utcnow() - timedelta(seconds=600 - seq * 5)).isoformat(),
    }
    base.update(kwargs)
    return base


async def seed():
    async with httpx.AsyncClient(timeout=10.0) as client:
        events = []
        seq = 0

        events.append(make_event("session_started", "planner", seq,
                                 task_description="Add type annotations to all functions in src/"))
        seq += 1

        for role, tool_name, latency_ms, cost_usd in TOOL_CALLS:
            call_id = str(uuid.uuid4())
            events.append(make_event("tool_call_started", role, seq,
                                     tool_call_id=call_id, tool_name=tool_name))
            seq += 1

            # 10% failure rate for drama
            if random.random() < 0.1:
                events.append(make_event("tool_call_failed", role, seq,
                                         tool_call_id=call_id, tool_name=tool_name,
                                         error_type="timeout", error_message="Tool timed out"))
            else:
                events.append(make_event("tool_call_finished", role, seq,
                                         tool_call_id=call_id, tool_name=tool_name,
                                         latency_ms=latency_ms + random.uniform(-50, 50),
                                         cost_usd=cost_usd, completion_tokens=random.randint(50, 500)))
            seq += 1

        for from_role, to_role in [("planner", "researcher"), ("researcher", "executor"), ("executor", "verifier")]:
            events.append(make_event("agent_handoff", from_role, seq,
                                     from_role=from_role, to_role=to_role))
            seq += 1

        events.append(make_event("session_completed", "verifier", seq,
                                 total_tokens=12450, total_cost_usd=0.0085, total_latency_ms=28400))

        r = await client.post("http://localhost:8002/events/batch", json=events)
        print(f"Seeded {len(events)} events for session {SESSION_ID}")
        print(f"Status: {r.status_code}")
        print(f"View at: http://localhost:8000/sessions/{SESSION_ID}")


if __name__ == "__main__":
    asyncio.run(seed())
