"""
A2A (Agent-to-Agent) coordinator.

Wraps the inter-agent artifact passing protocol from gemini-cli's a2a-server package.
For the current runtime, this serializes structured artifacts into the task inputs dict
that gets dispatched via Redis Streams. In a production deployment, this would use the
actual @google/gemini-cli a2a-server HTTP protocol.
"""

from __future__ import annotations

import uuid
from typing import Any


class A2AArtifact:
    """Structured artifact passed between agent roles."""

    def __init__(self, artifact_type: str, content: dict[str, Any], source_role: str) -> None:
        self.artifact_id = str(uuid.uuid4())
        self.artifact_type = artifact_type
        self.content = content
        self.source_role = source_role

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "content": self.content,
            "source_role": self.source_role,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "A2AArtifact":
        artifact = cls(
            artifact_type=data["artifact_type"],
            content=data["content"],
            source_role=data["source_role"],
        )
        artifact.artifact_id = data["artifact_id"]
        return artifact


class A2ACoordinator:
    """
    Manages structured artifact handoffs between agent roles.

    Handoff chain:
      Planner   → Researcher : task_graph artifact
      Researcher → Executor  : evidence_bundle artifact
      Executor  → Verifier   : patch_set artifact
      Verifier  → Executor   : verifier_feedback artifact (on failure)
    """

    def build_researcher_input(
        self,
        task_description: str,
        task_graph_outputs: dict[str, Any],
    ) -> dict[str, Any]:
        artifact = A2AArtifact(
            artifact_type="task_graph",
            content=task_graph_outputs,
            source_role="planner",
        )
        return {
            "task_description": task_description,
            "planner_artifact": artifact.to_dict(),
        }

    def build_executor_input(
        self,
        task_description: str,
        evidence_bundle: dict[str, Any],
        verifier_feedback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        artifact = A2AArtifact(
            artifact_type="evidence_bundle",
            content=evidence_bundle,
            source_role="researcher",
        )
        inputs: dict[str, Any] = {
            "task_description": task_description,
            "researcher_artifact": artifact.to_dict(),
        }
        if verifier_feedback:
            inputs["verifier_feedback"] = verifier_feedback
        return inputs

    def build_verifier_input(
        self,
        patch_set: dict[str, Any],
        commands_to_run: list[str],
    ) -> dict[str, Any]:
        artifact = A2AArtifact(
            artifact_type="patch_set",
            content={"patches": patch_set, "commands": commands_to_run},
            source_role="executor",
        )
        return {"executor_artifact": artifact.to_dict()}

    def extract_verifier_feedback(self, verifier_outputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "verdict": verifier_outputs.get("verdict", "fail"),
            "issues": verifier_outputs.get("issues", []),
            "test_results": verifier_outputs.get("test_results", {}),
            "retry_recommendation": verifier_outputs.get("retry_recommendation"),
        }
