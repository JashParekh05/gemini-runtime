from fastapi import FastAPI
from shared.telemetry.otel import setup_telemetry
from services.analytics.analytics.router import router

setup_telemetry("analytics")

app = FastAPI(title="gemini-runtime analytics", version="0.1.0")
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "analytics"}
