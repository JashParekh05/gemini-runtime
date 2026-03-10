#!/usr/bin/env bash
# gemini-cli hook: fires before each tool call
# Env vars injected by gemini-cli: TOOL_NAME, TOOL_ARGS, SESSION_ID, AGENT_ROLE, AGENT_ID

set -euo pipefail

INGESTION_URL="${INGESTION_URL:-http://localhost:8002}"

PAYLOAD=$(cat <<EOF
{
  "event_type": "tool_call_started",
  "session_id": "${SESSION_ID:-00000000-0000-0000-0000-000000000000}",
  "agent_id": "${AGENT_ID:-unknown}",
  "agent_role": "${AGENT_ROLE:-executor}",
  "tool_name": "${TOOL_NAME:-unknown}",
  "tool_args": ${TOOL_ARGS:-{}}
}
EOF
)

curl -sf -X POST "${INGESTION_URL}/events" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" \
  --max-time 2 \
  || true   # never block the tool call
