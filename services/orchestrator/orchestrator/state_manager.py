"""Postgres CRUD for Session and TaskGraph state."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.sessions import Session, SessionStatus
from shared.models.tasks import TaskGraph, TaskNode


class SessionStateManager:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_session(self, session: Session) -> None:
        await self._db.execute(
            text("""
                INSERT INTO sessions (session_id, created_at, updated_at, status,
                    task_description, initiator, metadata)
                VALUES (:session_id, :created_at, :updated_at, :status,
                    :task_description, :initiator, :metadata::jsonb)
            """),
            {
                "session_id": str(session.session_id),
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "status": session.status.value,
                "task_description": session.task_description,
                "initiator": session.initiator,
                "metadata": json.dumps(session.metadata),
            },
        )
        await self._db.commit()

    async def update_status(self, session_id: uuid.UUID, status: SessionStatus) -> None:
        await self._db.execute(
            text("UPDATE sessions SET status = :status WHERE session_id = :id"),
            {"status": status.value, "id": str(session_id)},
        )
        await self._db.commit()

    async def update_totals(
        self,
        session_id: uuid.UUID,
        tokens: int,
        cost_usd: float,
        latency_ms: float,
    ) -> None:
        await self._db.execute(
            text("""
                UPDATE sessions
                SET total_tokens = :tokens, total_cost_usd = :cost,
                    total_latency_ms = :latency
                WHERE session_id = :id
            """),
            {"tokens": tokens, "cost": cost_usd, "latency": latency_ms, "id": str(session_id)},
        )
        await self._db.commit()

    async def attach_graph(self, session_id: uuid.UUID, graph_id: uuid.UUID) -> None:
        await self._db.execute(
            text("UPDATE sessions SET task_graph_id = :gid WHERE session_id = :sid"),
            {"gid": str(graph_id), "sid": str(session_id)},
        )
        await self._db.commit()

    async def save_graph(self, graph: TaskGraph) -> None:
        nodes_json = json.dumps([n.model_dump(mode="json") for n in graph.nodes])
        await self._db.execute(
            text("""
                INSERT INTO task_graphs (graph_id, session_id, created_at, status, nodes, adjacency)
                VALUES (:graph_id, :session_id, :created_at, :status, :nodes::jsonb, :adjacency::jsonb)
                ON CONFLICT (graph_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    nodes = EXCLUDED.nodes
            """),
            {
                "graph_id": str(graph.graph_id),
                "session_id": str(graph.session_id),
                "created_at": graph.created_at,
                "status": graph.status.value,
                "nodes": nodes_json,
                "adjacency": json.dumps(graph.adjacency),
            },
        )
        await self._db.commit()

    async def get_session(self, session_id: uuid.UUID) -> dict | None:  # type: ignore[type-arg]
        result = await self._db.execute(
            text("SELECT * FROM sessions WHERE session_id = :id"),
            {"id": str(session_id)},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict]:  # type: ignore[type-arg]
        result = await self._db.execute(
            text("""
                SELECT session_id, created_at, status, task_description,
                       total_tokens, total_cost_usd, total_latency_ms
                FROM sessions
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        return [dict(r) for r in result.mappings()]
