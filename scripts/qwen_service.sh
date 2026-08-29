#!/bin/bash
#
# qwen_service.sh — start, stop and inspect the Qwen review service.
#
# Written to be safe to call from Automator, launchd, or a plain terminal.
# Automator gives a script none of your shell profile, so nothing here relies
# on PATH, on the working directory, or on a conda/venv already being active.
#
# Usage:
#   ./scripts/qwen_service.sh start [--no-wait] [--no-open] [--model ALIAS]
#   ./scripts/qwen_service.sh stop
#   ./scripts/qwen_service.sh restart
#   ./scripts/qwen_service.sh status
#   ./scripts/qwen_service.sh logs [llama|app]
#
# Two processes make up the service:
#   llama-server   holds the model in memory          (default port 8081)
#   server.py      FastAPI chat + review interface    (default port 8090)
#
# Port 8090 is deliberate. The FastAPI default of 8080 collides with the
# SmallThinker llama-server, and start_server.sh kills whatever occupies its
# port, so starting on 8080 would silently take SmallThinker down.

set -uo pipefail

# --- Locate the project, independent of the caller's directory -------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

# --- Automator safety: put Homebrew on PATH ourselves ----------------------
# A GUI-launched process inherits a bare PATH, so llama-server would not be
# found even though it works perfectly in Terminal.
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$PATH"

# --- Configuration ---------------------------------------------------------
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
APP_PY="$PROJECT_DIR/app/server.py"

APP_HOST="${QWEN_APP_HOST:-127.0.0.1}"
APP_PORT="${QWEN_APP_PORT:-8090}"

LLAMA_BIN="${LLAMA_SERVER_BIN:-llama-server}"
LLAMA_HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_SERVER_PORT:-8081}"
LLAMA_CTX="${LLAMA_SERVER_CTX:-32768}"
LLAMA_NGL="${LLAMA_SERVER_NGL:-99}"

HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
DEFAULT_MODEL="$HF_HUB/models--unsloth--Qwen3.8-27B-GGUF/snapshots/4ca720788d1e01f1bff70c033e0d0028fd02e502/Qwen3.8-27B-UD-Q4_K_XL.gguf"
MODEL="${QWEN_MODEL:-$DEFAULT_MODEL}"

RUN_DIR="$PROJECT_DIR/run"
LOG_DIR="$PROJECT_DIR/logs"
LLAMA_PID_FILE="$RUN_DIR/llama-server.pid"
APP_PID_FILE="$RUN_DIR/app-server.pid"
LLAMA_LOG="$LOG_DIR/llama-server.log"
APP_LOG="$LOG_DIR/app-server.log"

WAIT_FOR_READY=1
OPEN_BROWSER=1
STARTUP_TIMEOUT="${QWEN_STARTUP_TIMEOUT:-600}"

mkdir -p "$RUN_DIR" "$LOG_DIR"

# --- Notification ----------------------------------------------------------
# Automator apps have no terminal, so progress has to reach you some other way.
notify() {
  local title="$1" message="$2"
  if [[ -t 1 ]]; then
    echo "$message"
  else
    osascript -e "display notification \"${message//\"/\\\"}\" with title \"${title//\"/\\\"}\"" 2>/dev/null || true
  fi
}

log_line() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

# --- Process helpers -------------------------------------------------------
# Never kill by port alone. A PID file can go stale and be reused by an
# unrelated process, so every kill is guarded by a command-line match.
pid_is_alive() {
  local pid="${1:-}"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

pid_matches() {
  local pid="${1:-}" pattern="$2"
  [[ -n "$pid" ]] || return 1
  ps -p "$pid" -o command= 2>/dev/null | grep -q -- "$pattern"
}

read_pid() {
  local file="$1"
  [[ -f "$file" ]] && cat "$file" 2>/dev/null || echo ""
}

running_pid() {
  # Echo the pid from $1 only if it is alive and matches pattern $2.
  local pid
  pid="$(read_pid "$1")"
  if pid_is_alive "$pid" && pid_matches "$pid" "$2"; then
    echo "$pid"
  else
    echo ""
  fi
}

mismatched_pid() {
  # Echo the pid from $1 if it is alive but does NOT look like pattern $2.
  # This is the dangerous case: either the pid was reused by something
  # unrelated, or our process is running under a command line we do not
  # recognise. Either way it must be reported rather than passed over in
  # silence, or a live server gets orphaned while the pid file is deleted.
  local pid
  pid="$(read_pid "$1")"
  if pid_is_alive "$pid" && ! pid_matches "$pid" "$2"; then
    echo "$pid"
  else
    echo ""
  fi
}

port_in_use() {
  lsof -ti:"$1" >/dev/null 2>&1
}

port_owner() {
  lsof -ti:"$1" 2>/dev/null | head -1
}

http_ok() {
  curl -s -o /dev/null -m 2 "$1" 2>/dev/null
}

llama_ready() {
  http_ok "http://$LLAMA_HOST:$LLAMA_PORT/health" \
    || http_ok "http://$LLAMA_HOST:$LLAMA_PORT/props"
}

app_ready() {
  http_ok "http://$APP_HOST:$APP_PORT/v1/models"
}

stop_pid() {
  # Graceful TERM, then KILL if it will not go. $1 pid, $2 label.
  local pid="$1" label="$2"
  log_line "Stopping $label (pid $pid)..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    pid_is_alive "$pid" || { log_line "$label stopped."; return 0; }
    sleep 0.5
  done
  log_line "$label did not stop; sending KILL."
  kill -9 "$pid" 2>/dev/null || true
  sleep 1
  pid_is_alive "$pid" && { log_line "WARNING: $label (pid $pid) is still alive."; return 1; }
  log_line "$label stopped."
}

# --- Preflight -------------------------------------------------------------
preflight() {
  local problems=0

  if [[ ! -x "$VENV_PYTHON" ]]; then
    log_line "ERROR: venv python not found at $VENV_PYTHON"
    log_line "       This is what made the earlier Automator attempt fail:"
    log_line "       the system python has no fastapi installed."
    problems=1
  elif ! "$VENV_PYTHON" -c "import fastapi, uvicorn" 2>/dev/null; then
    log_line "ERROR: fastapi/uvicorn missing from the venv."
    log_line "       Fix: $VENV_PYTHON -m pip install fastapi uvicorn python-multipart"
    problems=1
  fi

  if [[ ! -f "$APP_PY" ]]; then
    log_line "ERROR: $APP_PY not found."
    problems=1
  fi

  if [[ "$MODEL" == *.gguf ]]; then
    if [[ ! -f "$MODEL" ]]; then
      log_line "ERROR: model file not found: $MODEL"
      problems=1
    fi
    if ! command -v "$LLAMA_BIN" >/dev/null 2>&1; then
      log_line "ERROR: $LLAMA_BIN not on PATH."
      log_line "       PATH is: $PATH"
      log_line "       Fix: brew install llama.cpp"
      problems=1
    fi
  fi

  return $problems
}

# --- Start -----------------------------------------------------------------
start_llama() {
  if [[ "$MODEL" != *.gguf ]]; then
    log_line "Model is not a GGUF; llama-server is not needed."
    return 0
  fi

  local existing
  existing="$(running_pid "$LLAMA_PID_FILE" "llama-server")"
  if [[ -n "$existing" ]] && llama_ready; then
    log_line "llama-server already running (pid $existing)."
    return 0
  fi

  if llama_ready; then
    log_line "Reusing the llama-server already answering on port $LLAMA_PORT."
    # Not ours, so do not record a pid: stop must not kill it.
    rm -f "$LLAMA_PID_FILE"
    return 0
  fi

  if port_in_use "$LLAMA_PORT"; then
    log_line "ERROR: port $LLAMA_PORT is held by pid $(port_owner "$LLAMA_PORT") but is not answering."
    log_line "       Refusing to kill an unknown process. Free the port or set LLAMA_SERVER_PORT."
    return 1
  fi

  log_line "Starting llama-server on port $LLAMA_PORT ($(basename "$MODEL"))..."
  nohup "$LLAMA_BIN" \
    --model "$MODEL" \
    --host "$LLAMA_HOST" \
    --port "$LLAMA_PORT" \
    --ctx-size "$LLAMA_CTX" \
    --n-gpu-layers "$LLAMA_NGL" \
    --jinja \
    >> "$LLAMA_LOG" 2>&1 < /dev/null &
  echo $! > "$LLAMA_PID_FILE"
  log_line "llama-server pid $(cat "$LLAMA_PID_FILE"), log: $LLAMA_LOG"

  [[ "$WAIT_FOR_READY" -eq 1 ]] || return 0

  local pid deadline
  pid="$(cat "$LLAMA_PID_FILE")"
  deadline=$(( $(date +%s) + STARTUP_TIMEOUT ))
  while [[ $(date +%s) -lt $deadline ]]; do
    llama_ready && { log_line "llama-server ready."; return 0; }
    if ! pid_is_alive "$pid"; then
      log_line "ERROR: llama-server exited during startup. Last lines:"
      tail -n 20 "$LLAMA_LOG" 2>/dev/null
      rm -f "$LLAMA_PID_FILE"
      return 1
    fi
    sleep 2
  done
  log_line "ERROR: llama-server did not become ready within ${STARTUP_TIMEOUT}s."
  return 1
}

start_app() {
  local existing
  existing="$(running_pid "$APP_PID_FILE" "server.py")"
  if [[ -n "$existing" ]]; then
    log_line "App server already running (pid $existing)."
    return 0
  fi

  if port_in_use "$APP_PORT"; then
    log_line "ERROR: port $APP_PORT is already in use by pid $(port_owner "$APP_PORT")."
    log_line "       Refusing to kill it. Stop it yourself or set QWEN_APP_PORT."
    return 1
  fi

  log_line "Starting the app server on port $APP_PORT..."
  cd "$PROJECT_DIR" || return 1

  QWEN_LLM_BACKEND="$([[ "$MODEL" == *.gguf ]] && echo llama-server || echo mlx)" \
  LLAMA_SERVER_URL="http://$LLAMA_HOST:$LLAMA_PORT" \
  nohup "$VENV_PYTHON" "$APP_PY" \
    --model "$MODEL" \
    --host "$APP_HOST" \
    --port "$APP_PORT" \
    >> "$APP_LOG" 2>&1 < /dev/null &
  echo $! > "$APP_PID_FILE"
  log_line "App server pid $(cat "$APP_PID_FILE"), log: $APP_LOG"

  [[ "$WAIT_FOR_READY" -eq 1 ]] || return 0

  local pid deadline
  pid="$(cat "$APP_PID_FILE")"
  deadline=$(( $(date +%s) + 120 ))
  while [[ $(date +%s) -lt $deadline ]]; do
    app_ready && { log_line "App server ready."; return 0; }
    if ! pid_is_alive "$pid"; then
      log_line "ERROR: app server exited during startup. Last lines:"
      tail -n 20 "$APP_LOG" 2>/dev/null
      rm -f "$APP_PID_FILE"
      return 1
    fi
    sleep 1
  done
  log_line "ERROR: app server did not become ready in time. See $APP_LOG"
  return 1
}

cmd_start() {
  log_line "=== Starting Qwen review ==="

  if ! preflight; then
    notify "Qwen review" "Startup failed: see $APP_LOG"
    return 1
  fi

  if ! start_llama; then
    notify "Qwen review" "llama-server failed to start. See $LLAMA_LOG"
    return 1
  fi

  if ! start_app; then
    notify "Qwen review" "App server failed to start. See $APP_LOG"
    return 1
  fi

  local url="http://$APP_HOST:$APP_PORT"
  if [[ "$OPEN_BROWSER" -eq 1 ]]; then
    open "$url" 2>/dev/null || true
  fi
  notify "Qwen review" "Ready at $url"
  log_line "=== Ready at $url ==="
  return 0
}

# --- Stop ------------------------------------------------------------------
cmd_stop() {
  log_line "=== Stopping Qwen review ==="
  local stopped=0

  local app_pid app_odd
  app_pid="$(running_pid "$APP_PID_FILE" "server.py")"
  app_odd="$(mismatched_pid "$APP_PID_FILE" "server.py")"
  if [[ -n "$app_pid" ]]; then
    stop_pid "$app_pid" "app server"
    stopped=1
  elif [[ -n "$app_odd" ]]; then
    log_line "WARNING: pid $app_odd from $APP_PID_FILE is alive but does not look"
    log_line "         like the app server. Not killing it. Check with:"
    log_line "           ps -p $app_odd -o command="
    log_line "         If port $APP_PORT stays busy, stop that process yourself."
  else
    log_line "App server is not running."
  fi
  rm -f "$APP_PID_FILE"

  local llama_pid llama_odd
  llama_pid="$(running_pid "$LLAMA_PID_FILE" "llama-server")"
  llama_odd="$(mismatched_pid "$LLAMA_PID_FILE" "llama-server")"
  if [[ -n "$llama_pid" ]]; then
    stop_pid "$llama_pid" "llama-server"
    stopped=1
  elif [[ -n "$llama_odd" ]]; then
    log_line "WARNING: pid $llama_odd from $LLAMA_PID_FILE is alive but does not"
    log_line "         look like llama-server. Not killing it. Check with:"
    log_line "           ps -p $llama_odd -o command="
  else
    if llama_ready; then
      log_line "A llama-server is answering on port $LLAMA_PORT but this script did not start it."
      log_line "Leaving it alone. Stop it where you started it."
    else
      log_line "llama-server is not running."
    fi
  fi
  rm -f "$LLAMA_PID_FILE"

  if [[ "$stopped" -eq 1 ]]; then
    notify "Qwen review" "Stopped."
  else
    notify "Qwen review" "Nothing was running."
  fi
  log_line "=== Stopped ==="
  return 0
}

# --- Status ----------------------------------------------------------------
cmd_status() {
  local app_pid llama_pid
  app_pid="$(running_pid "$APP_PID_FILE" "server.py")"
  llama_pid="$(running_pid "$LLAMA_PID_FILE" "llama-server")"

  echo "Project:     $PROJECT_DIR"
  echo "Model:       $(basename "$MODEL")"
  echo ""

  if [[ -n "$llama_pid" ]]; then
    echo "llama-server: running (pid $llama_pid, port $LLAMA_PORT)"
  elif llama_ready; then
    echo "llama-server: running on port $LLAMA_PORT, started elsewhere"
  else
    echo "llama-server: stopped"
  fi
  echo "  responding: $(llama_ready && echo yes || echo no)"

  if [[ -n "$app_pid" ]]; then
    echo "app server:   running (pid $app_pid, port $APP_PORT)"
  else
    echo "app server:   stopped"
  fi
  echo "  responding: $(app_ready && echo yes || echo no)"
  echo ""
  echo "UI:          http://$APP_HOST:$APP_PORT"
  echo "Logs:        $LLAMA_LOG"
  echo "             $APP_LOG"
}

cmd_logs() {
  case "${1:-app}" in
    llama) tail -n 40 -f "$LLAMA_LOG" ;;
    app|*)  tail -n 40 -f "$APP_LOG" ;;
  esac
}

# --- Argument parsing ------------------------------------------------------
COMMAND="${1:-status}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-wait) WAIT_FOR_READY=0; shift ;;
    --no-open) OPEN_BROWSER=0; shift ;;
    --port)    APP_PORT="$2"; shift 2 ;;
    --llama-port) LLAMA_PORT="$2"; shift 2 ;;
    --model)   MODEL="$2"; shift 2 ;;
    llama|app) LOG_TARGET="$1"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

case "$COMMAND" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_stop; sleep 2; cmd_start ;;
  status)  cmd_status ;;
  logs)    cmd_logs "${LOG_TARGET:-app}" ;;
  -h|--help|help)
    sed -n '2,30p' "$0"
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    echo "Use: start | stop | restart | status | logs" >&2
    exit 1
    ;;
esac
