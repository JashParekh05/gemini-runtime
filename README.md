# gemini-runtime

A distributed multi-agent orchestration runtime and observability platform built on top of [`google-gemini/gemini-cli`](https://github.com/google-gemini/gemini-cli).

Instead of running one agent end-to-end, gemini-runtime splits work across four specialized roles — **planner**, **researcher**, **executor**, **verifier** — each backed by a custom MCP server and coordinated through a fault-tolerant DAG scheduler. Every tool call, token, latency number, and failure gets captured, stored in ClickHouse, and surfaced through a dashboard with session replay and regression detection.

---

## How it works

```
POST /sessions  →  Orchestrator (DAG scheduler)
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼  (parallel when deps allow)
          Planner   Researcher  Executor
              │         │         │
              └─────────┼─────────┘
                        ▼
                    Verifier
                        │
              ┌─────────┴───────────┐
              ▼                     ▼
          pass → done          fail → re-queue Executor
                                     with verifier feedback
```

Each agent spawns `gemini-cli` with `--output-format stream-json` and an MCP server for its role:

```bash
gemini \
  --prompt @/tmp/task.md \
  --output-format stream-json \
  --mcp-server ./mcp/researcher-tools/dist/ \
  --yolo
```

The NDJSON stream gets parsed line-by-line — every `tool_call` and `tool_result` event opens/closes an OpenTelemetry span and emits an event to `stream:events` (Redis). The ingestion service consumes that stream and writes to ClickHouse (analytics) and Postgres (state).

---

## Architecture

| Layer | Technology |
|---|---|
| Agent runtime | `gemini-cli` subprocess (`--output-format stream-json`) |
| Agent tools | MCP servers (TypeScript, one per role) |
| Agent handoffs | `@google/gemini-cli` A2A protocol |
| Orchestration | Python + FastAPI + asyncio |
| Task queue | Redis Streams (consumer groups, at-least-once delivery) |
| Session state | PostgreSQL + SQLAlchemy async |
| Event analytics | ClickHouse (MergeTree, SummingMergeTree materialized views) |
| Tracing | OpenTelemetry (extends gemini-cli's built-in OTel) |
| Dashboard | FastAPI + Jinja2 + vanilla JS |

---

## Services

| Service | Port | Description |
|---|---|---|
| `api` | 8000 | Dashboard + public gateway |
| `orchestrator` | 8001 | DAG scheduler, session management |
| `ingestion` | 8002 | Redis Stream consumer → ClickHouse + Postgres |
| `analytics` | 8003 | Query service (latency, cost, SLOs, regression) |
| postgres | 5432 | Session + task state |
| clickhouse | 8123/9000 | Event analytics |
| redis | 6379 | Streams + messaging |

---

## Getting started

```bash
# 1. Copy env file and add your Gemini API key
cp .env.example .env
# edit GEMINI_API_KEY in .env

# 2. Start everything
make up

# 3. Open the dashboard
open http://localhost:8000

# 4. Submit a task via the dashboard, or directly:
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"task_description": "Add type annotations to all functions in src/"}'

# 5. Seed a demo session (no API key needed)
make seed

# 6. Check service health
make health
```

---

## MCP tools

Each agent role has a dedicated TypeScript MCP server registered via `gemini-extension.json`:

| Role | MCP Server | Tools |
|---|---|---|
| Planner | `mcp/planner-tools` | `inspect_project_structure`, `estimate_task_complexity`, `check_existing_tests` |
| Researcher | `mcp/researcher-tools` | `read_workspace_file`, `search_codebase`, `list_workspace_files`, `get_git_history` |
| Executor | `mcp/executor-tools` | `write_file`, `apply_unified_diff`, `run_shell_command`, `delete_file` |
| Verifier | `mcp/verifier-tools` | `run_pytest`, `run_mypy`, `run_ruff`, `check_test_coverage` |

Build all MCP servers:
```bash
make mcp-install && make mcp-build
```

---

## Observability

### Session trace
Every tool call produces an OpenTelemetry span:
- Attributes: `agent.role`, `tool.name`, `session.id`, `latency_ms`, `tokens.completion`, `cost_usd`

### SLO tracking
```bash
curl http://localhost:8000/api/v1/analytics/slo
```
Returns compliance rate + error budget for:
- `planner_latency` — 95% of planning tasks in < 30s
- `verifier_parse_success` — 99% of verifier calls return structured verdict
- `system_completion` — 95% of sessions complete successfully

### Regression detection
```bash
curl "http://localhost:8000/api/v1/analytics/regression?baseline=<id>&target=<id>"
```
Compares cost, p95 latency, and error rate between two sessions. Flags regression if any metric increases more than 20%.

### Session replay
```bash
# CLI
python scripts/replay_session.py <session_id>

# Browser
open http://localhost:8000/sessions/<session_id>/replay
```

---

## Lifecycle hooks

gemini-cli hooks fire at tool call boundaries without forking the CLI:

```
hooks/tool_call_before.sh   →  emits tool_call_started to ingestion
hooks/tool_call_after.sh    →  emits tool_call_finished or tool_call_failed
hooks/session_end.sh        →  emits session_completed or session_failed
```

---

## Project structure

```
shared/         shared Python package (models, db clients, messaging, telemetry)
services/
  orchestrator/ DAG scheduler + session state
  agent_worker/ gemini-cli subprocess wrapper + role agents
  ingestion/    Redis stream consumer → ClickHouse + Postgres
  analytics/    latency/cost/SLO/regression query service
  api/          gateway + dashboard
mcp/            TypeScript MCP server extensions (one per agent role)
hooks/          gemini-cli lifecycle hooks
infra/          postgres and clickhouse init SQL, redis config
scripts/        seed_demo.py, replay_session.py, health_check.py
```

---

## Development

```bash
make lint      # ruff + mypy
make test      # pytest with coverage
make fmt       # ruff format
make migrate   # alembic upgrade head
make logs      # docker compose logs -f
```
