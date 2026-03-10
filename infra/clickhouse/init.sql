-- gemini-runtime ClickHouse schema

-- ── events (append-only) ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS events
(
    event_id            UUID,
    session_id          UUID,
    agent_id            String,
    agent_role          LowCardinality(String),
    event_type          LowCardinality(String),
    sequence_number     UInt64,
    emitted_at          DateTime64(3, 'UTC'),
    server_received_at  DateTime64(3, 'UTC'),
    payload             String   -- JSON blob for per-type flexibility
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(emitted_at)
ORDER BY (session_id, sequence_number)
TTL emitted_at + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- ── tool_call_metrics ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tool_call_metrics
(
    session_id          UUID,
    agent_id            String,
    agent_role          LowCardinality(String),
    tool_name           LowCardinality(String),
    started_at          DateTime64(3, 'UTC'),
    latency_ms          Float64,
    prompt_tokens       UInt32,
    completion_tokens   UInt32,
    cost_usd            Float64,
    status              LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(started_at)
ORDER BY (session_id, started_at)
SETTINGS index_granularity = 8192;

-- ── session_cost_mv (fast per-session rollup) ──────────────────────────────────

CREATE MATERIALIZED VIEW IF NOT EXISTS session_cost_mv
ENGINE = SummingMergeTree()
ORDER BY session_id
AS
SELECT
    session_id,
    sum(cost_usd)                             AS total_cost_usd,
    sum(prompt_tokens + completion_tokens)    AS total_tokens,
    count()                                   AS total_tool_calls,
    countIf(status = 'failed')                AS failed_tool_calls
FROM tool_call_metrics
GROUP BY session_id;

-- ── latency_percentiles (queried by analytics service) ─────────────────────────
-- This is a convenience view; actual percentile queries use quantile() on tool_call_metrics

CREATE VIEW IF NOT EXISTS latency_percentiles AS
SELECT
    tool_name,
    agent_role,
    quantile(0.50)(latency_ms) AS p50,
    quantile(0.95)(latency_ms) AS p95,
    quantile(0.99)(latency_ms) AS p99,
    count()                    AS total_calls,
    countIf(status = 'failed') AS failed_calls,
    avg(cost_usd)              AS avg_cost_usd
FROM tool_call_metrics
GROUP BY tool_name, agent_role;
