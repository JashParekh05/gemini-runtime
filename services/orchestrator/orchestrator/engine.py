"""
OrchestrationEngine — core DAG scheduling loop.

Lifecycle per session:
  1. Load session + task graph from Postgres
  2. Run DAGResolver to find ready nodes
  3. Dispatch each ready node to the appropriate agent task stream
  4. Await results from stream:results
  5. Mark nodes complete/failed, advance DAG
  6. Repeat until all nodes done or terminal failure
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime

from shared.db.postgres import get_session_factory
from shared.db.redis_client import get_redis
from shared.messaging.schemas import StreamMessage, TaskDispatch, TaskResult
from shared.messaging.streams import STREAM_RESULTS, TASK_STREAM, StreamConsumer, StreamProducer
from shared.models.events import AgentHandoffEvent, AgentRole, SessionCompletedEvent, SessionFailedEvent
from shared.models.sessions import Session, SessionStatus
from shared.models.tasks import TaskGraph, TaskNode, TaskStatus
from shared.telemetry.otel import get_tracer
from services.orchestrator.orchestrator.a2a_coordinator import A2ACoordinator
from services.orchestrator.orchestrator.dag import DAGResolver
from services.orchestrator.orchestrator.state_manager import SessionStateManager

logger = logging.getLogger(__name__)
tracer = get_tracer("orchestrator")


class OrchestrationEngine:
    def __init__(self) -> None:
        self._coordinator = A2ACoordinator()
        self._active_sessions: dict[str, asyncio.Task] = {}  # type: ignore[type-arg]

    async def submit(self, session: Session, graph: TaskGraph) -> None:
        """Create a session in Postgres and start the DAG execution loop."""
        factory = get_session_factory()
        async with factory() as db:
            sm = SessionStateManager(db)
            await sm.create_session(session)
            await sm.save_graph(graph)
            await sm.attach_graph(session.session_id, graph.graph_id)

        task = asyncio.create_task(
            self._run_session(session, graph),
            name=f"session-{session.session_id}",
        )
        self._active_sessions[str(session.session_id)] = task
        task.add_done_callback(lambda t: self._active_sessions.pop(str(session.session_id), None))

    async def _run_session(self, session: Session, graph: TaskGraph) -> None:
        with tracer.start_as_current_span("session", attributes={"session.id": str(session.session_id)}):
            dag = DAGResolver(graph)
            redis = get_redis()
            producer = StreamProducer(redis)

            factory = get_session_factory()
            async with factory() as db:
                sm = SessionStateManager(db)
                await sm.update_status(session.session_id, SessionStatus.planning)

            total_tokens = 0
            total_cost = 0.0
            session_start = datetime.utcnow()

            try:
                while not dag.is_complete() and not dag.has_terminal_failure():
                    ready = dag.get_ready_nodes()
                    if not ready:
                        # All pending nodes have unresolved dependencies — wait
                        await asyncio.sleep(0.5)
                        continue

                    # Dispatch all ready nodes concurrently
                    results = await asyncio.gather(
                        *[self._dispatch_node(node, session, graph, producer) for node in ready],
                        return_exceptions=True,
                    )

                    for node, result in zip(ready, results):
                        if isinstance(result, Exception):
                            logger.error("Node %s failed: %s", node.task_id, result)
                            dag.mark_failed(node.task_id)
                        else:
                            task_result: TaskResult = result
                            if task_result.status == "completed":
                                dag.mark_complete(node.task_id, task_result.outputs)
                                total_tokens += task_result.total_tokens
                                total_cost += task_result.cost_usd
                            else:
                                dag.mark_failed(node.task_id)

                    # Persist updated graph
                    async with factory() as db:
                        sm = SessionStateManager(db)
                        await sm.save_graph(graph)

                total_latency = (datetime.utcnow() - session_start).total_seconds() * 1000

                if dag.is_complete():
                    await self._emit_completed(session, producer, total_tokens, total_cost, total_latency)
                    async with factory() as db:
                        sm = SessionStateManager(db)
                        await sm.update_status(session.session_id, SessionStatus.completed)
                        await sm.update_totals(session.session_id, total_tokens, total_cost, total_latency)
                else:
                    await self._emit_failed(session, producer, "terminal task failure")
                    async with factory() as db:
                        sm = SessionStateManager(db)
                        await sm.update_status(session.session_id, SessionStatus.failed)

            except Exception:
                logger.exception("Session %s crashed", session.session_id)
                await self._emit_failed(session, producer, "orchestration error")
                async with factory() as db:
                    sm = SessionStateManager(db)
                    await sm.update_status(session.session_id, SessionStatus.failed)

    async def _dispatch_node(
        self,
        node: TaskNode,
        session: Session,
        graph: TaskGraph,
        producer: StreamProducer,
    ) -> TaskResult:
        agent_id = f"{node.agent_role}-{str(session.session_id)[:8]}"
        stream = TASK_STREAM[node.agent_role.value]

        # Enrich inputs via A2A coordinator
        inputs = self._enrich_inputs(node, graph)

        dispatch = TaskDispatch(
            session_id=str(session.session_id),
            task_id=str(node.task_id),
            task_type=node.task_type.value,
            agent_role=node.agent_role.value,
            description=node.description,
            inputs=inputs,
            retry_count=node.retry_count,
        )
        await producer.publish_raw(stream, "TaskDispatch", dispatch.model_dump())
        logger.info("Dispatched task %s to %s", node.task_id, stream)

        # Wait for result from stream:results
        result = await self._await_result(str(node.task_id), agent_id)

        # Emit handoff event if we know the next role
        next_role = self._next_role(node.agent_role)
        if next_role:
            await producer.publish_raw(
                "stream:events",
                "Event",
                AgentHandoffEvent(
                    session_id=session.session_id,
                    agent_id=agent_id,
                    agent_role=node.agent_role,
                    from_role=node.agent_role,
                    to_role=AgentRole(next_role),
                    artifact_ref=str(node.task_id),
                ).model_dump(mode="json"),
            )

        return result

    def _enrich_inputs(self, node: TaskNode, graph: TaskGraph) -> dict:  # type: ignore[type-arg]
        """Add outputs from dependency nodes into this node's inputs via A2A."""
        inputs = dict(node.inputs)
        for dep_id in node.dependencies:
            dep_node = graph.get_node(dep_id)
            if dep_node and dep_node.outputs:
                inputs[f"{dep_node.agent_role}_outputs"] = dep_node.outputs
        return inputs

    async def _await_result(self, task_id: str, agent_id: str, timeout: int = 300) -> TaskResult:
        """Poll stream:results for the result of a specific task."""
        redis = get_redis()
        deadline = asyncio.get_event_loop().time() + timeout
        last_id = "0"

        while asyncio.get_event_loop().time() < deadline:
            messages = await redis.xread({STREAM_RESULTS: last_id}, count=50, block=1000)
            for _stream, msgs in (messages or []):
                for msg_id, fields in msgs:
                    last_id = msg_id
                    try:
                        payload = json.loads(fields.get("payload", "{}"))
                        if payload.get("task_id") == task_id:
                            return TaskResult(**payload)
                    except Exception:
                        pass

        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

    async def _emit_completed(
        self,
        session: Session,
        producer: StreamProducer,
        tokens: int,
        cost: float,
        latency_ms: float,
    ) -> None:
        await producer.publish_raw(
            "stream:events",
            "Event",
            SessionCompletedEvent(
                session_id=session.session_id,
                agent_id="orchestrator",
                agent_role=AgentRole.planner,
                total_tokens=tokens,
                total_cost_usd=cost,
                total_latency_ms=latency_ms,
            ).model_dump(mode="json"),
        )

    async def _emit_failed(
        self,
        session: Session,
        producer: StreamProducer,
        reason: str,
    ) -> None:
        await producer.publish_raw(
            "stream:events",
            "Event",
            SessionFailedEvent(
                session_id=session.session_id,
                agent_id="orchestrator",
                agent_role=AgentRole.planner,
                failure_reason=reason,
            ).model_dump(mode="json"),
        )

    @staticmethod
    def _next_role(current: AgentRole) -> str | None:
        chain = {
            AgentRole.planner: AgentRole.researcher,
            AgentRole.researcher: AgentRole.executor,
            AgentRole.executor: AgentRole.verifier,
        }
        next_role = chain.get(current)
        return next_role.value if next_role else None
