FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/orchestrator/ ./services/orchestrator/

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8001

CMD ["uvicorn", "services.orchestrator.orchestrator.main:app", "--host", "0.0.0.0", "--port", "8001"]
