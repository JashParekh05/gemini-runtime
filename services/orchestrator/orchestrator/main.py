from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from shared.db.postgres import close_engine
from shared.db.redis_client import close_redis
from shared.telemetry.otel import setup_telemetry
from services.orchestrator.orchestrator.router import router

setup_telemetry("orchestrator")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Orchestrator started")
    yield
    await close_engine()
    await close_redis()
    logger.info("Orchestrator stopped")


app = FastAPI(title="gemini-runtime orchestrator", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}
