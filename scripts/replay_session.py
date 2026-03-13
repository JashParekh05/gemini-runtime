#!/usr/bin/env python3
"""CLI tool for replaying a session's events step-by-step."""

import asyncio
import sys
import time

import httpx

API_URL = "http://localhost:8000"

ROLE_COLORS = {
    "planner": "\033[94m",    # blue
    "researcher": "\033[92m", # green
    "executor": "\033[93m",   # yellow
    "verifier": "\033[91m",   # red
}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

EVENT_ICONS = {
    "session_started": "▶",
    "tool_call_started": "⚙",
    "tool_call_finished": "✓",
    "tool_call_failed": "✗",
    "agent_handoff": "→",
    "session_completed": "■",
    "session_failed": "■",
}


async def replay(session_id: str, delay: float = 0.1) -> None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{API_URL}/api/v1/sessions/{session_id}/replay")
        if r.status_code == 404:
            print(f"Session {session_id} not found.")
            return
        events = r.json()

    print(f"\n{BOLD}Replaying session {session_id}{RESET}")
    print(f"{DIM}{len(events)} events{RESET}\n")

    for ev in events:
        role = ev.get("agent_role", "unknown")
        color = ROLE_COLORS.get(role, "")
        icon = EVENT_ICONS.get(ev["event_type"], "•")
        ts = ev.get("emitted_at", "")[:19].replace("T", " ")

        line = f"{color}{role:12}{RESET} {icon} {ev['event_type']:<28}"

        if ev["event_type"] == "tool_call_finished":
            line += f"  {DIM}latency={ev.get('latency_ms',0):.0f}ms  cost=${ev.get('cost_usd',0):.6f}{RESET}"
        elif ev["event_type"] == "tool_call_failed":
            line += f"  {DIM}error={ev.get('error_message','')[:40]}{RESET}"
        elif ev["event_type"] in ("session_completed", "session_failed"):
            line += f"  {DIM}tokens={ev.get('total_tokens',0)}  cost=${ev.get('total_cost_usd',0):.5f}{RESET}"

        line += f"  {DIM}{ts}{RESET}"
        print(line)
        time.sleep(delay)

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/replay_session.py <session_id> [delay_seconds]")
        sys.exit(1)
    sid = sys.argv[1]
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    asyncio.run(replay(sid, delay))
