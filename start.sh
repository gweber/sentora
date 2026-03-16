#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

log()  { echo -e "${CYAN}[start.sh]${NC} $*"; }
ok()   { echo -e "${GREEN}[start.sh]${NC} $*"; }
warn() { echo -e "${YELLOW}[start.sh]${NC} $*"; }
err()  { echo -e "${RED}[start.sh]${NC} $*" >&2; }

# ── Cleanup on exit ───────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  warn "Shutting down…"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  ok "All processes stopped."
}
trap cleanup EXIT INT TERM

# ── Dependency checks ─────────────────────────────────────────────────────────
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    err "Required command not found: $1"
    exit 1
  fi
}
check_cmd python3
check_cmd npm

# Prefer the venv uvicorn if it exists
UVICORN="$BACKEND/.venv/bin/uvicorn"
if [[ ! -x "$UVICORN" ]]; then
  check_cmd uvicorn
  UVICORN="uvicorn"
fi

# ── MongoDB check (warn only — might be in Docker) ───────────────────────────
if ! nc -z localhost 27017 2>/dev/null; then
  warn "MongoDB does not appear to be running on localhost:27017."
  warn "Start it with: docker run -d -p 27017:27017 mongo:7"
  warn "Continuing anyway — the backend will fail to connect if Mongo is absent."
fi

# ── Backend ───────────────────────────────────────────────────────────────────
log "Starting backend (FastAPI on :5002)…"
(
  cd "$BACKEND"
  # Load .env so uvicorn inherits it
  if [[ -f "$ROOT/.env" ]]; then
    set -a; source "$ROOT/.env"; set +a
  fi
  "$UVICORN" main:app --host 0.0.0.0 --port 5002 --reload \
    2>&1 | sed "s/^/$(echo -e "${GREEN}[backend]${NC}") /"
) &
PIDS+=($!)

# ── Frontend ──────────────────────────────────────────────────────────────────
log "Starting frontend dev server (Vite on :5003)…"
(
  cd "$FRONTEND"
  npm run dev 2>&1 | sed "s/^/$(echo -e "${CYAN}[frontend]${NC}") /"
) &
PIDS+=($!)

# ── Ready ─────────────────────────────────────────────────────────────────────
ok "Both services started."
echo ""
echo -e "  ${CYAN}Frontend${NC}  →  http://localhost:5003"
echo -e "  ${CYAN}Backend API${NC} →  http://localhost:5002/api/docs"
echo ""
echo "Press Ctrl+C to stop."

# Wait for either process to exit (crash detection)
wait -n 2>/dev/null || wait
