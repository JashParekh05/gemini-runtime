from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.postgres import get_db
from shared.models.sessions import Session
from shared.models.tasks import TaskGraph, TaskNode, TaskStatus, TaskType
from shared.models.events import AgentRole
from services.orchestrator.orchestrator.engine import OrchestrationEngine
from services.orchestrator.orchestrator.state_manager import SessionStateManager

router = APIRouter(tags=["sessions"])
_engine = OrchestrationEngine()


class CreateSessionRequest(BaseModel):
    task_description: str
    initiator: str = "api"
    metadata: dict[str, Any] = {}


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str


@router.post("/sessions", response_model=CreateSessionResponse, status_code=202)
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    session = Session(
        task_description=req.task_description,
        initiator=req.initiator,
        metadata=req.metadata,
    )

    # Build an initial 4-node linear graph: plan → research → execute → verify
    plan_id = uuid.uuid4()
    research_id = uuid.uuid4()
    execute_id = uuid.uuid4()
    verify_id = uuid.uuid4()

    nodes = [
        TaskNode(task_id=plan_id, task_type=TaskType.plan, agent_role=AgentRole.planner,
                 description=f"Decompose task: {req.task_description}", dependencies=[]),
        TaskNode(task_id=research_id, task_type=TaskType.research, agent_role=AgentRole.researcher,
                 description="Research codebase and gather context", dependencies=[plan_id]),
        TaskNode(task_id=execute_id, task_type=TaskType.implement, agent_role=AgentRole.executor,
                 description="Implement changes based on research", dependencies=[research_id]),
        TaskNode(task_id=verify_id, task_type=TaskType.verify, agent_role=AgentRole.verifier,
                 description="Verify implementation and run tests", dependencies=[execute_id]),
    ]

    graph = TaskGraph(session_id=session.session_id, nodes=nodes)
    await _engine.submit(session, graph)

    return CreateSessionResponse(
        session_id=str(session.session_id),
        status="accepted",
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    sm = SessionStateManager(db)
    session = await sm.get_session(uuid.UUID(session_id))
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {k: str(v) if not isinstance(v, (str, int, float, bool, dict, list, type(None))) else v
            for k, v in session.items()}


@router.get("/sessions")
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    sm = SessionStateManager(db)
    rows = await sm.list_sessions(limit=limit, offset=offset)
    return [{k: str(v) if not isinstance(v, (str, int, float, bool, dict, list, type(None))) else v
             for k, v in r.items()} for r in rows]
