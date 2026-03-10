#!/usr/bin/env bash
# gemini-cli hook: fires when a session ends
# Env vars: SESSION_ID, SESSION_STATUS (completed|failed), AGENT_ROLE, AGENT_ID,
#           TOTAL_TOKENS, TOTAL_COST_USD, TOTAL_LATENCY_MS, FAILURE_REASON

set -euo pipefail

INGESTION_URL="${INGESTION_URL:-http://localhost:8002}"
STATUS="${SESSION_STATUS:-completed}"

if [ "${STATUS}" = "completed" ]; then
  PAYLOAD=$(cat <<EOF
{
  "event_type": "session_completed",
  "session_id": "${SESSION_ID:-00000000-0000-0000-0000-000000000000}",
  "agent_id": "${AGENT_ID:-unknown}",
  "agent_role": "${AGENT_ROLE:-executor}",
  "total_tokens": ${TOTAL_TOKENS:-0},
  "total_cost_usd": ${TOTAL_COST_USD:-0.0},
  "total_latency_ms": ${TOTAL_LATENCY_MS:-0.0}
}
EOF
)
else
  PAYLOAD=$(cat <<EOF
{
  "event_type": "session_failed",
  "session_id": "${SESSION_ID:-00000000-0000-0000-0000-000000000000}",
  "agent_id": "${AGENT_ID:-unknown}",
  "agent_role": "${AGENT_ROLE:-executor}",
  "failure_reason": "${FAILURE_REASON:-unknown}",
  "total_tokens": ${TOTAL_TOKENS:-0},
  "total_cost_usd": ${TOTAL_COST_USD:-0.0},
  "total_latency_ms": ${TOTAL_LATENCY_MS:-0.0}
}
EOF
)
fi

curl -sf -X POST "${INGESTION_URL}/events" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" \
  --max-time 2 \
  || true
