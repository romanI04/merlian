#!/bin/bash
# Merlian installer for macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/romanI04/merlian/main/install.sh | bash
set -euo pipefail

INSTALL_DIR="$HOME/.merlian-app"
REPO_URL="https://github.com/romanI04/merlian.git"
LAUNCHER="$HOME/.local/bin/merlian"

echo ""
echo "  Merlian — search your visual memory"
echo "  ====================================="
echo ""

# 1. Check Python >= 3.10
echo "[1/8] Checking Python..."
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 not found. Install from https://python.org or: brew install python@3.12"
  exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 10 ]]; then
  echo "ERROR: Python >= 3.10 required (found $PY_VERSION)"
  exit 1
fi
echo "  Python $PY_VERSION OK"

# 2. Check Node >= 18
echo "[2/8] Checking Node.js..."
if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install from https://nodejs.org or: brew install node"
  exit 1
fi
NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
if [[ "$NODE_MAJOR" -lt 18 ]]; then
  echo "ERROR: Node >= 18 required (found $(node -v))"
  exit 1
fi
echo "  Node $(node -v) OK"

# 3. Check Xcode CLI tools
echo "[3/8] Checking Xcode CLI tools..."
if ! xcode-select -p &>/dev/null; then
  echo "Xcode CLI tools needed for PyObjC (Apple Vision OCR)."
  echo "Installing... (this may take a few minutes)"
  xcode-select --install 2>/dev/null || true
  echo "After installation completes, re-run this installer."
  exit 1
fi
echo "  Xcode CLI tools OK"

# 4. Clone or update repo
echo "[4/8] Setting up Merlian..."
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "  Updating existing installation..."
  cd "$INSTALL_DIR"
  git pull --rebase origin main || true
else
  echo "  Cloning repository..."
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# 5. Create Python venv
echo "[5/8] Setting up Python environment..."
cd "$INSTALL_DIR/engine"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

# 6. Install Python deps
echo "[6/8] Installing Python dependencies (this may take a few minutes)..."
pip install --upgrade pip -q
pip install -r requirements.txt

# 7. Pre-download CLIP model
echo "[7/8] Pre-downloading AI model (~577 MB, one-time)..."
python3 -c "
import open_clip
print('  Downloading model weights...')
open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
print('  Model cached.')
" 2>&1

# 8. Install npm deps + build frontend
echo "[8/8] Building frontend..."
cd "$INSTALL_DIR/dispict"
npm install --silent 2>/dev/null
npm run build --silent 2>/dev/null

# Create launcher
mkdir -p "$(dirname "$LAUNCHER")"
cat > "$LAUNCHER" << 'LAUNCHER_SCRIPT'
#!/bin/bash
# Merlian launcher
set -euo pipefail

INSTALL_DIR="$HOME/.merlian-app"
DATA_DIR="$HOME/Library/Application Support/Merlian"

cd "$INSTALL_DIR/engine"
source .venv/bin/activate

# Find available port
PORT=${MERLIAN_PORT:-8008}
while lsof -i ":$PORT" &>/dev/null; do
  PORT=$((PORT + 1))
done

# Write port for frontend discovery
mkdir -p "$DATA_DIR"
echo "$PORT" > "$DATA_DIR/api_port"

echo "Merlian starting on http://127.0.0.1:$PORT"
echo "Press Ctrl+C to stop."

# Start server (serves both API + built frontend)
cleanup() {
  rm -f "$DATA_DIR/api_port"
  echo ""
  echo "Merlian stopped."
}
trap cleanup EXIT

MERLIAN_SERVE_FRONTEND=1 uvicorn server:app --host 127.0.0.1 --port "$PORT" &
SERVER_PID=$!

# Wait for health
for _ in {1..60}; do
  if curl -sSf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Open browser
open "http://127.0.0.1:$PORT"

wait $SERVER_PID
LAUNCHER_SCRIPT
chmod +x "$LAUNCHER"

echo ""
echo "  Installation complete!"
echo ""
echo "  To start Merlian:"
echo "    merlian"
echo ""
echo "  Or run directly:"
echo "    $LAUNCHER"
echo ""
echo "  Data stored at: ~/Library/Application Support/Merlian/"
echo ""
