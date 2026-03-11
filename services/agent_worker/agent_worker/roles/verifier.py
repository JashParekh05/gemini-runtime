from __future__ import annotations

import json
import logging
from typing import Any

from shared.models.events import AgentRole
from services.agent_worker.agent_worker.base_agent import BaseAgent

logger = logging.getLogger(__name__)

VERIFIER_SYSTEM_PROMPT = """
You are a software verification agent. Your job is to check that the implementation
is correct, complete, and passes all tests.

Use your tools (run_pytest, run_mypy, run_ruff, check_test_coverage) to verify the changes.
Be thorough — check for regressions, edge cases, and code quality issues.

You MUST respond with valid JSON:
{
  "verdict": "pass | fail | partial",
  "issues": [
    {
      "severity": "error | warning | info",
      "file": "<file path or null>",
      "line": <line number or null>,
      "message": "<description of the issue>"
    }
  ],
  "test_results": {
    "passed": <int>,
    "failed": <int>,
    "errors": <int>,
    "coverage_pct": <float or null>
  },
  "retry_recommendation": "<specific instructions for the executor if verdict is fail, else null>"
}

Return ONLY the JSON.
"""


class VerifierAgent(BaseAgent):
    role = AgentRole.verifier

    def _mcp_server_path(self) -> str | None:
        return "./mcp/verifier-tools/dist"

    def build_prompt(self, task_description: str, inputs: dict[str, Any]) -> str:
        executor_outputs = inputs.get("executor_outputs", {})
        context = f"Task that was implemented: {task_description}\n"
        if executor_outputs:
            context += f"\nImplementation summary:\n{json.dumps(executor_outputs, indent=2)}"
        return f"{VERIFIER_SYSTEM_PROMPT}\n\n{context}"

    def parse_output(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        try:
            data = json.loads(content)
            # Normalize: ensure required keys exist
            data.setdefault("verdict", "fail")
            data.setdefault("issues", [])
            data.setdefault("test_results", {"passed": 0, "failed": 0, "errors": 0})
            return data
        except json.JSONDecodeError:
            logger.warning("Verifier output was not valid JSON")
            return {
                "raw_output": content,
                "verdict": "fail",
                "issues": [{"severity": "error", "message": "Verifier returned non-JSON output"}],
                "test_results": {"passed": 0, "failed": 0, "errors": 1},
            }
