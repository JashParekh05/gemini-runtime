FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/ingestion/ ./services/ingestion/

RUN pip install --no-cache-dir -e ".[dev]" && \
    pip install --no-cache-dir uvicorn

EXPOSE 8002

CMD ["uvicorn", "services.ingestion.ingestion.main:app", "--host", "0.0.0.0", "--port", "8002"]
