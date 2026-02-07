#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENGINE_DIR="$ROOT_DIR/engine"
UI_DIR="$ROOT_DIR/dispict"

PORT_API=${PORT_API:-8008}
PORT_UI=${PORT_UI:-5173}
HOST_UI=${HOST_UI:-127.0.0.1}
DEV_MODE=true

# Parse --dev / --prod flag
for arg in "$@"; do
  case "$arg" in
    --prod|--production) DEV_MODE=false ;;
    --dev) DEV_MODE=true ;;
  esac
done

# Check Python
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
  echo "[merlian] ERROR: Python >= 3.10 required (found $PY_VERSION)"
  exit 1
fi

# Check Node
if ! command -v node &>/dev/null; then
  echo "[merlian] ERROR: Node.js not found"
  exit 1
fi

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

# Find available port for API
while lsof -i ":$PORT_API" &>/dev/null 2>&1; do
  PORT_API=$((PORT_API + 1))
done

echo "[merlian] starting engine API on :$PORT_API"

if [[ "$DEV_MODE" == "true" ]]; then
  uvicorn server:app --host 127.0.0.1 --port "$PORT_API" --reload >/tmp/merlian-api.log 2>&1 &
else
  MERLIAN_SERVE_FRONTEND=1 uvicorn server:app --host 127.0.0.1 --port "$PORT_API" >/tmp/merlian-api.log 2>&1 &
fi
API_PID=$!

# Wait for health (up to 30s)
for _ in {1..60}; do
  if curl -sSf "http://127.0.0.1:$PORT_API/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Warm model (best effort)
curl -s -X POST "http://127.0.0.1:$PORT_API/warm" -H 'content-type: application/json' -d '"auto"' >/dev/null 2>&1 || true

if [[ "$DEV_MODE" == "true" ]]; then
  echo "[merlian] starting UI dev server on $HOST_UI:$PORT_UI"
  cd "$UI_DIR"
  npm -s install >/dev/null
  VITE_LOCAL_API_URL="http://127.0.0.1:$PORT_API" npm run -s dev -- --host "$HOST_UI" --port "$PORT_UI" >/tmp/merlian-ui.log 2>&1 &
  UI_PID=$!

  echo ""
  echo "Merlian is running (dev mode):"
  echo "  Demo gallery: http://$HOST_UI:$PORT_UI/#/demo"
  echo "  Local search: http://$HOST_UI:$PORT_UI/#/local"
  echo "  API:          http://127.0.0.1:$PORT_API"
else
  echo ""
  echo "Merlian is running (production mode):"
  echo "  App: http://127.0.0.1:$PORT_API"
fi

echo ""
echo "Logs:"
echo "  API: /tmp/merlian-api.log"
if [[ "$DEV_MODE" == "true" ]]; then
  echo "  UI:  /tmp/merlian-ui.log"
fi
echo ""
echo "Press Ctrl+C to stop."

wait
