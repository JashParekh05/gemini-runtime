# Install both Python and Node.js (for gemini-cli)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g @google/gemini-cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/agent_worker/ ./services/agent_worker/
COPY mcp/ ./mcp/

# Build MCP servers
RUN cd mcp && npm install --workspaces && npm run build --workspaces 2>/dev/null || true

RUN pip install --no-cache-dir -e ".[dev]"

CMD ["python", "-m", "services.agent_worker.agent_worker.main"]
