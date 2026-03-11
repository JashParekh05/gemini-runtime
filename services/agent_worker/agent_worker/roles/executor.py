from __future__ import annotations

import json
import logging
from typing import Any

from shared.models.events import AgentRole
from services.agent_worker.agent_worker.base_agent import BaseAgent

logger = logging.getLogger(__name__)

EXECUTOR_SYSTEM_PROMPT = """
You are a software implementation agent. Your job is to write code changes that fulfill
the given task based on the researcher's findings.

Use your tools (apply_unified_diff, write_file, run_shell_command) to make the changes.
Follow the existing code style exactly. Write tests for any new code.

You MUST respond with valid JSON:
{
  "patches": [
    {
      "file_path": "<relative path>",
      "patch_type": "unified_diff | full_replace | new_file",
      "content": "<the patch or full file content>",
      "description": "<what this change does>"
    }
  ],
  "new_files": [],
  "commands_to_run": ["<commands to run after applying patches, e.g. pip install, npm install>"],
  "summary": "<one sentence describing what was changed>"
}

Return ONLY the JSON.
"""


class ExecutorAgent(BaseAgent):
    role = AgentRole.executor

    def _mcp_server_path(self) -> str | None:
        return "./mcp/executor-tools/dist"

    def build_prompt(self, task_description: str, inputs: dict[str, Any]) -> str:
        researcher_outputs = inputs.get("researcher_outputs", {})
        verifier_feedback = inputs.get("verifier_feedback")

        context = f"Task: {task_description}\n"
        if researcher_outputs:
            context += f"\nResearch findings:\n{json.dumps(researcher_outputs, indent=2)}"
        if verifier_feedback:
            context += f"\n\n⚠️  Previous attempt failed verification. Feedback:\n{json.dumps(verifier_feedback, indent=2)}"
            context += "\n\nPlease address ALL issues listed above in your implementation."

        return f"{EXECUTOR_SYSTEM_PROMPT}\n\n{context}"

    def parse_output(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Executor output was not valid JSON")
            return {"raw_output": content, "patches": [], "commands_to_run": []}
