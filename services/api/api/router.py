from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, WebSocket
from pydantic import BaseModel

from shared.config import settings
from services.api.api.ws import session_event_stream

router = APIRouter()
logger = logging.getLogger(__name__)


# ── proxy helpers ──────────────────────────────────────────────────────────────

async def _get(url: str) -> Any:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.json()


async def _post(url: str, data: dict) -> Any:  # type: ignore[type-arg]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=data)
        r.raise_for_status()
        return r.json()


# ── sessions ───────────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    task_description: str
    initiator: str = "api"
    metadata: dict[str, Any] = {}


@router.post("/sessions", status_code=202)
async def create_session(req: CreateSessionRequest) -> Any:
    return await _post(f"{settings.orchestrator_url}/sessions", req.model_dump())


@router.get("/sessions")
async def list_sessions(limit: int = Query(default=20), offset: int = Query(default=0)) -> Any:
    return await _get(f"{settings.orchestrator_url}/sessions?limit={limit}&offset={offset}")


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Any:
    return await _get(f"{settings.orchestrator_url}/sessions/{session_id}")


@router.get("/sessions/{session_id}/trace")
async def session_trace(session_id: str) -> Any:
    return await _get(f"{settings.analytics_url}/analytics/sessions/{session_id}/trace")


@router.get("/sessions/{session_id}/cost")
async def session_cost(session_id: str) -> Any:
    return await _get(f"{settings.analytics_url}/analytics/sessions/{session_id}/cost")


@router.get("/sessions/{session_id}/latency")
async def session_latency(session_id: str) -> Any:
    return await _get(f"{settings.analytics_url}/analytics/sessions/{session_id}/latency")


@router.get("/sessions/{session_id}/replay")
async def session_replay(session_id: str) -> Any:
    """Return ordered event list for client-side replay."""
    return await _get(f"{settings.analytics_url}/analytics/sessions/{session_id}/trace")


# ── analytics ──────────────────────────────────────────────────────────────────

@router.get("/analytics/tools")
async def tool_stats(hours: int = Query(default=24)) -> Any:
    return await _get(f"{settings.analytics_url}/analytics/tools?hours={hours}")


@router.get("/analytics/regression")
async def regression(
    baseline: str = Query(...),
    target: str = Query(...),
    threshold: float = Query(default=20.0),
) -> Any:
    return await _get(
        f"{settings.analytics_url}/analytics/regression?baseline={baseline}&target={target}&threshold={threshold}"
    )


@router.get("/analytics/slo")
async def slo(hours: int = Query(default=24)) -> Any:
    return await _get(f"{settings.analytics_url}/analytics/slo?hours={hours}")


# ── websocket ──────────────────────────────────────────────────────────────────

@router.websocket("/ws/sessions/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str, replay: bool = False) -> None:
    await session_event_stream(websocket, session_id, replay=replay)
