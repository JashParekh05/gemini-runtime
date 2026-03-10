-- gemini-runtime Postgres schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── sessions ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    session_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    task_description TEXT NOT NULL,
    task_graph_id   UUID,
    initiator       VARCHAR(255) NOT NULL DEFAULT 'api',
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    total_cost_usd  NUMERIC(12, 8) NOT NULL DEFAULT 0,
    total_latency_ms NUMERIC(12, 2) NOT NULL DEFAULT 0,
    metadata        JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at DESC);

-- ── task_graphs ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS task_graphs (
    graph_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    nodes       JSONB NOT NULL DEFAULT '[]',
    adjacency   JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_task_graphs_session_id ON task_graphs(session_id);

-- ── task_nodes ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS task_nodes (
    task_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    graph_id        UUID NOT NULL REFERENCES task_graphs(graph_id) ON DELETE CASCADE,
    session_id      UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    task_type       VARCHAR(20) NOT NULL,
    agent_role      VARCHAR(20) NOT NULL,
    description     TEXT NOT NULL,
    dependencies    UUID[] NOT NULL DEFAULT '{}',
    inputs          JSONB NOT NULL DEFAULT '{}',
    outputs         JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    assigned_agent_id VARCHAR(255),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3
);

CREATE INDEX IF NOT EXISTS idx_task_nodes_graph_status ON task_nodes(graph_id, status);
CREATE INDEX IF NOT EXISTS idx_task_nodes_session ON task_nodes(session_id);

-- ── tool_invocations ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tool_invocations (
    invocation_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    agent_id        VARCHAR(255) NOT NULL,
    tool_name       VARCHAR(255) NOT NULL,
    args            JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    latency_ms      NUMERIC(12, 2),
    prompt_tokens   INTEGER,
    completion_tokens INTEGER,
    cost_usd        NUMERIC(12, 8),
    status          VARCHAR(20) NOT NULL DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_tool_invocations_session_started ON tool_invocations(session_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_invocations_tool_name ON tool_invocations(tool_name);

-- ── auto-update updated_at ─────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
