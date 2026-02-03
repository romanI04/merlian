#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENGINE_DIR="$ROOT_DIR/engine"
UI_DIR="$ROOT_DIR/ui"

PORT_API=${PORT_API:-8008}
PORT_UI=${PORT_UI:-5173}
HOST_UI=${HOST_UI:-127.0.0.1}

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "${UI_PID:-}" ]]; then kill "$UI_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

cd "$ENGINE_DIR"

if [[ ! -d .venv ]]; then
  echo "[merlian] creating venv"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip -q install -r requirements.txt

echo "[merlian] starting engine API on :$PORT_API"
uvicorn server:app --host 127.0.0.1 --port "$PORT_API" >/tmp/merlian-api.log 2>&1 &
API_PID=$!

# Wait for health
for _ in {1..40}; do
  if curl -sSf "http://127.0.0.1:$PORT_API/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

# Warm model (best effort)
curl -s -X POST "http://127.0.0.1:$PORT_API/warm" -H 'content-type: application/json' -d '"auto"' >/dev/null 2>&1 || true

echo "[merlian] starting UI on $HOST_UI:$PORT_UI"
cd "$UI_DIR"
npm -s install >/dev/null
VITE_LOCAL_API_URL="http://127.0.0.1:$PORT_API" npm run -s dev -- --host "$HOST_UI" --port "$PORT_UI" >/tmp/merlian-ui.log 2>&1 &
UI_PID=$!

echo ""
echo "Merlian is running:"
echo "  Demo gallery: http://$HOST_UI:$PORT_UI/#/demo"
echo "  Local search: http://$HOST_UI:$PORT_UI/#/local"
echo ""
echo "Logs:"
echo "  API: /tmp/merlian-api.log"
echo "  UI:  /tmp/merlian-ui.log"
echo ""
echo "Press Ctrl+C to stop."

wait
