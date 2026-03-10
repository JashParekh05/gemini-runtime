#!/usr/bin/env bash
# gemini-cli hook: fires after each tool call completes or fails
# Env vars: TOOL_NAME, TOOL_CALL_ID, TOOL_STATUS (success|error), LATENCY_MS,
#           TOOL_ERROR, SESSION_ID, AGENT_ROLE, AGENT_ID

set -euo pipefail

INGESTION_URL="${INGESTION_URL:-http://localhost:8002}"
STATUS="${TOOL_STATUS:-success}"
TOOL_CALL_ID="${TOOL_CALL_ID:-$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)}"

if [ "${STATUS}" = "success" ]; then
  EVENT_TYPE="tool_call_finished"
  PAYLOAD=$(cat <<EOF
{
  "event_type": "${EVENT_TYPE}",
  "session_id": "${SESSION_ID:-00000000-0000-0000-0000-000000000000}",
  "agent_id": "${AGENT_ID:-unknown}",
  "agent_role": "${AGENT_ROLE:-executor}",
  "tool_call_id": "${TOOL_CALL_ID}",
  "tool_name": "${TOOL_NAME:-unknown}",
  "latency_ms": ${LATENCY_MS:-0}
}
EOF
)
else
  EVENT_TYPE="tool_call_failed"
  PAYLOAD=$(cat <<EOF
{
  "event_type": "${EVENT_TYPE}",
  "session_id": "${SESSION_ID:-00000000-0000-0000-0000-000000000000}",
  "agent_id": "${AGENT_ID:-unknown}",
  "agent_role": "${AGENT_ROLE:-executor}",
  "tool_call_id": "${TOOL_CALL_ID}",
  "tool_name": "${TOOL_NAME:-unknown}",
  "error_type": "tool_error",
  "error_message": "${TOOL_ERROR:-unknown error}",
  "retry_count": 0
}
EOF
)
fi

curl -sf -X POST "${INGESTION_URL}/events" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" \
  --max-time 2 \
  || true
