from __future__ import annotations

import json
import logging
from typing import Any

from shared.models.events import AgentRole
from services.agent_worker.agent_worker.base_agent import BaseAgent

logger = logging.getLogger(__name__)

RESEARCHER_SYSTEM_PROMPT = """
You are a codebase research agent. Your job is to understand the existing code and gather
everything an implementation agent will need to complete the task.

Use your tools (read_workspace_file, search_codebase, index_symbols, get_git_history) to
explore the codebase. Be thorough but focused — only gather what is directly relevant.

You MUST respond with valid JSON:
{
  "findings": [
    {
      "file_path": "<relative path>",
      "relevance": "high | medium | low",
      "summary": "<what this file does and why it matters>",
      "snippet": "<key code snippet if applicable>"
    }
  ],
  "recommended_entry_points": ["<file paths>"],
  "context_for_executor": "<concise summary of what the executor needs to know>",
  "potential_risks": ["<anything that could go wrong>"]
}

Return ONLY the JSON.
"""


class ResearchAgent(BaseAgent):
    role = AgentRole.researcher

    def _mcp_server_path(self) -> str | None:
        return "./mcp/researcher-tools/dist"

    def build_prompt(self, task_description: str, inputs: dict[str, Any]) -> str:
        planner_outputs = inputs.get("planner_outputs", {})
        context = f"Task: {task_description}\n"
        if planner_outputs:
            context += f"\nPlanner's breakdown:\n{json.dumps(planner_outputs, indent=2)}"
        return f"{RESEARCHER_SYSTEM_PROMPT}\n\n{context}"

    def parse_output(self, content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("Researcher output was not valid JSON")
            return {"raw_output": content, "findings": [], "context_for_executor": content}
