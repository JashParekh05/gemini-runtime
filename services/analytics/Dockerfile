FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/analytics/ ./services/analytics/
RUN pip install --no-cache-dir -e ".[dev]"
EXPOSE 8003
CMD ["uvicorn", "services.analytics.analytics.main:app", "--host", "0.0.0.0", "--port", "8003"]
