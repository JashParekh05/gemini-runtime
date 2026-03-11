import uuid
import pytest
from shared.models.tasks import TaskGraph, TaskNode, TaskStatus, TaskType
from shared.models.events import AgentRole
from services.orchestrator.orchestrator.dag import DAGResolver


def make_node(role: AgentRole, deps: list[uuid.UUID] | None = None) -> TaskNode:
    return TaskNode(
        task_type=TaskType.plan,
        agent_role=role,
        description="test",
        dependencies=deps or [],
    )


def test_no_deps_ready():
    n1 = make_node(AgentRole.planner)
    n2 = make_node(AgentRole.researcher)
    graph = TaskGraph(session_id=uuid.uuid4(), nodes=[n1, n2])
    dag = DAGResolver(graph)
    ready = dag.get_ready_nodes()
    assert len(ready) == 2


def test_dep_not_ready_until_parent_complete():
    n1 = make_node(AgentRole.planner)
    n2 = make_node(AgentRole.researcher, deps=[n1.task_id])
    graph = TaskGraph(session_id=uuid.uuid4(), nodes=[n1, n2])
    dag = DAGResolver(graph)
    ready = dag.get_ready_nodes()
    assert len(ready) == 1
    assert ready[0].task_id == n1.task_id

    dag.mark_complete(n1.task_id, {})
    ready = dag.get_ready_nodes()
    assert len(ready) == 1
    assert ready[0].task_id == n2.task_id


def test_retry_increments_count():
    n1 = make_node(AgentRole.executor)
    graph = TaskGraph(session_id=uuid.uuid4(), nodes=[n1])
    dag = DAGResolver(graph)
    dag.mark_failed(n1.task_id, retry=True)
    node = graph.get_node(n1.task_id)
    assert node is not None
    assert node.status == TaskStatus.pending
    assert node.retry_count == 1


def test_max_retries_marks_failed():
    n1 = make_node(AgentRole.executor)
    n1 = n1.model_copy(update={"retry_count": 3, "max_retries": 3})
    graph = TaskGraph(session_id=uuid.uuid4(), nodes=[n1])
    dag = DAGResolver(graph)
    dag.mark_failed(n1.task_id, retry=True)
    node = graph.get_node(n1.task_id)
    assert node is not None
    assert node.status == TaskStatus.failed
