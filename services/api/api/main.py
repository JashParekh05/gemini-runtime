from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shared.telemetry.otel import setup_telemetry
from services.api.api.router import router

setup_telemetry("api")
logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "dashboard" / "templates"
STATIC_DIR = Path(__file__).parent.parent / "dashboard" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("API gateway started")
    yield
    logger.info("API gateway stopped")


app = FastAPI(title="gemini-runtime", version="0.1.0", lifespan=lifespan)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.include_router(router, prefix="/api/v1")


# ── dashboard routes ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("sessions.html", {"request": request})


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: str) -> HTMLResponse:
    return templates.TemplateResponse("trace.html", {"request": request, "session_id": session_id})


@app.get("/sessions/{session_id}/replay", response_class=HTMLResponse)
async def session_replay_view(request: Request, session_id: str) -> HTMLResponse:
    return templates.TemplateResponse("replay.html", {"request": request, "session_id": session_id})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}
