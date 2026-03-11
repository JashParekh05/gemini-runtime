from __future__ import annotations

import json
import logging
from typing import Any

from shared.models.events import AgentRole
from services.agent_worker.agent_worker.base_agent import BaseAgent

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """
You are a software engineering task planner. Your job is to decompose a high-level task into
a precise, ordered set of subtasks with explicit dependencies.

You MUST respond with valid JSON matching this schema exactly:
{
  "task_graph": {
    "nodes": [
      {
        "task_type": "research | implement | verify",
        "agent_role": "researcher | executor | verifier",
        "description": "<specific actionable description>",
        "dependencies": ["<task_id of upstream node>"],
        "inputs": {}
      }
    ]
  },
  "summary": "<one sentence describing the overall approach>"
}

Rules:
- Be specific. Each node should be doable by a single focused agent call.
- Keep the graph shallow — prefer parallel nodes over deep chains where possible.
- Always end with a verifier node that checks all executor outputs.
- Return ONLY the JSON. No markdown, no explanation.
"""


class PlannerAgent(BaseAgent):
    role = AgentRole.planner

    def _mcp_server_path(self) -> str | None:
        return "./mcp/planner-tools/dist"

    def build_prompt(self, task_description: str, inputs: dict[str, Any]) -> str:
        return f"{PLANNER_SYSTEM_PROMPT}\n\nTask to decompose:\n{task_description}"

    def parse_output(self, content: str) -> dict[str, Any]:
        # Strip markdown fences if present
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError:
            logger.warning("Planner output was not valid JSON, returning raw")
            return {"raw_output": content, "task_graph": {"nodes": []}}
