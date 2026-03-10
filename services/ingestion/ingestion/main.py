from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from shared.telemetry.otel import setup_telemetry
from services.ingestion.ingestion.router import router
from services.ingestion.ingestion.consumer import start_consumer

setup_telemetry("ingestion")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    task = asyncio.create_task(start_consumer())
    logger.info("Ingestion service started")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Ingestion service stopped")


app = FastAPI(title="gemini-runtime ingestion", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingestion"}
