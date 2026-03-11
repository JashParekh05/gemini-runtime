"""DAG resolver — topological ordering and readiness tracking for TaskGraph nodes."""

from __future__ import annotations

import uuid

from shared.models.tasks import TaskGraph, TaskNode, TaskStatus


class DAGResolver:
    def __init__(self, graph: TaskGraph) -> None:
        self._graph = graph
        # index for O(1) lookup
        self._nodes: dict[uuid.UUID, TaskNode] = {n.task_id: n for n in graph.nodes}

    def get_ready_nodes(self) -> list[TaskNode]:
        """Return nodes whose dependencies are all completed and status is pending."""
        ready = []
        for node in self._nodes.values():
            if node.status != TaskStatus.pending:
                continue
            if all(
                self._nodes[dep_id].status == TaskStatus.completed
                for dep_id in node.dependencies
                if dep_id in self._nodes
            ):
                ready.append(node)
        return ready

    def mark_running(self, task_id: uuid.UUID, agent_id: str) -> None:
        node = self._nodes[task_id]
        self._nodes[task_id] = node.model_copy(
            update={"status": TaskStatus.running, "assigned_agent_id": agent_id}
        )
        self._sync_graph()

    def mark_complete(self, task_id: uuid.UUID, outputs: dict) -> None:  # type: ignore[type-arg]
        from datetime import datetime

        node = self._nodes[task_id]
        self._nodes[task_id] = node.model_copy(
            update={
                "status": TaskStatus.completed,
                "outputs": outputs,
                "completed_at": datetime.utcnow(),
            }
        )
        self._sync_graph()

    def mark_failed(self, task_id: uuid.UUID, retry: bool = True) -> None:
        node = self._nodes[task_id]
        if retry and node.retry_count < node.max_retries:
            self._nodes[task_id] = node.model_copy(
                update={
                    "status": TaskStatus.pending,
                    "retry_count": node.retry_count + 1,
                }
            )
        else:
            self._nodes[task_id] = node.model_copy(update={"status": TaskStatus.failed})
        self._sync_graph()

    def is_complete(self) -> bool:
        return all(n.status == TaskStatus.completed for n in self._nodes.values())

    def has_terminal_failure(self) -> bool:
        return any(n.status == TaskStatus.failed for n in self._nodes.values())

    def _sync_graph(self) -> None:
        self._graph.nodes[:] = list(self._nodes.values())
