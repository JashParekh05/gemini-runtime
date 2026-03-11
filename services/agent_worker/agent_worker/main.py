"""Agent worker entry point. Reads AGENT_ROLE env var and starts the appropriate consumer."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid

from shared.config import settings
from shared.db.redis_client import get_redis
from shared.messaging.schemas import StreamMessage, TaskDispatch, TaskResult
from shared.messaging.streams import STREAM_RESULTS, TASK_STREAM, StreamConsumer, StreamProducer
from shared.telemetry.otel import setup_telemetry

logger = logging.getLogger(__name__)


def get_agent_class(role: str):  # type: ignore[return]
    if role == "planner":
        from services.agent_worker.agent_worker.roles.planner import PlannerAgent
        return PlannerAgent
    elif role == "researcher":
        from services.agent_worker.agent_worker.roles.researcher import ResearchAgent
        return ResearchAgent
    elif role == "executor":
        from services.agent_worker.agent_worker.roles.executor import ExecutorAgent
        return ExecutorAgent
    elif role == "verifier":
        from services.agent_worker.agent_worker.roles.verifier import VerifierAgent
        return VerifierAgent
    else:
        raise ValueError(f"Unknown agent role: {role}")


async def handle_task(msg_id: str, message: StreamMessage) -> None:
    if message.payload_type != "TaskDispatch":
        return

    dispatch = TaskDispatch(**message.payload)
    role = dispatch.agent_role
    session_id = uuid.UUID(dispatch.session_id)
    task_id = uuid.UUID(dispatch.task_id)

    AgentClass = get_agent_class(role)
    agent = AgentClass(session_id=session_id)

    logger.info("Starting task %s (%s) for session %s", task_id, role, session_id)
    result = await agent.run(
        task_id=task_id,
        task_description=dispatch.description,
        inputs=dispatch.inputs,
    )

    # Publish result back to orchestrator
    redis = get_redis()
    producer = StreamProducer(redis)
    task_result = TaskResult(
        session_id=dispatch.session_id,
        task_id=dispatch.task_id,
        agent_id=f"{role}-{dispatch.session_id[:8]}",
        status=result.status.value,
        outputs=result.outputs or {},
        error=result.error,
        total_tokens=result.total_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )
    await producer.publish_raw(STREAM_RESULTS, "TaskResult", task_result.model_dump())
    logger.info("Task %s completed with status %s", task_id, result.status)


async def main() -> None:
    role = settings.agent_role
    setup_telemetry(f"agent_worker_{role}")
    logging.basicConfig(level=settings.log_level)

    stream = TASK_STREAM.get(role)
    if not stream:
        raise ValueError(f"No task stream for role: {role}")

    redis = get_redis()
    consumer = StreamConsumer(
        redis=redis,
        stream=stream,
        group=f"cg:{role}-workers",
        consumer_name=f"{role}-worker-{os.getpid()}",
    )
    logger.info("Agent worker starting: role=%s stream=%s", role, stream)
    await consumer.consume(handle_task)


if __name__ == "__main__":
    asyncio.run(main())
