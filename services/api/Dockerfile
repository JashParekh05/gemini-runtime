FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/api/ ./services/api/
RUN pip install --no-cache-dir -e ".[dev]" && pip install jinja2 aiofiles
EXPOSE 8000
CMD ["uvicorn", "services.api.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
