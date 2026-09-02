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
#                                    [--passes N] [--effort low|medium|high|xhigh]
#                                    [--vision]
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
# Synthesis passes. Findings rotate between passes, so one pass finds roughly
# half of what the model can see; three passes, each validated before merging,
# kept 7/9 concerns and added five items on the run that settled this. The cost
# is linear in generation time, and quality is worth more than time here.
# Override for a quick triage pass with --passes 1.
REVIEW_PASSES="${REVIEW_PASSES:-3}"
# Passed through explicitly and logged, like the pass count: an inherited
# variable that silently fails to reach the app server is exactly the kind of
# thing that cost a day here. Empty leaves the chat template's own default.
LLAMA_REASONING_EFFORT="${LLAMA_REASONING_EFFORT:-}"
# Vision: off unless asked for. It needs llama-server started with a projector,
# so the flag has to be set here rather than per review -- the app server can
# only use what the model server was given.
QWEN_VISION_TABLES="${QWEN_VISION_TABLES:-0}"
LLAMA_NGL="${LLAMA_SERVER_NGL:-99}"

HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
DEFAULT_MODEL="$HF_HUB/models--unsloth--Qwen3.8-27B-GGUF/snapshots/4ca720788d1e01f1bff70c033e0d0028fd02e502/Qwen3.8-27B-UD-Q4_K_XL.gguf"
MODEL="${QWEN_MODEL:-$DEFAULT_MODEL}"

RUN_DIR="$PROJECT_DIR/run"
LOG_DIR="$PROJECT_DIR/logs"
LLAMA_PID_FILE="$RUN_DIR/llama-server.pid"
APP_PID_FILE="$RUN_DIR/app-server.pid"
# Fingerprint of the Python the running server imported. server.py imports
# review_pipeline once at start-up, so a server left running across an edit
# serves superseded code with nothing to show it. One ran for thirteen hours
# that way, across four reviews, because "start" on an already-running server
# correctly reports "already running" and does nothing.
CODE_FINGERPRINT_FILE="$RUN_DIR/code.fingerprint"
LLAMA_LOG="$LOG_DIR/llama-server.log"
APP_LOG="$LOG_DIR/app-server.log"
SERVICE_LOG="$LOG_DIR/service.log"

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
  local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  echo "$msg"
  echo "$msg" >> "$SERVICE_LOG" 2>/dev/null || true
}

# Automator's "Run Shell Script" shows only stderr in its error dialog, and
# only when the script exits non-zero. Diagnostics written to stdout are
# discarded, which produces the useless message:
#     The action "Run Shell Script" encountered an error: ""
# So on any failing exit, replay the recent log to stderr. Interactive runs
# already have it on screen and are left alone.
on_exit() {
  local rc=$?
  if [[ $rc -ne 0 && ! -t 2 ]]; then
    {
      echo "qwen_service.sh ${COMMAND:-?} failed (exit $rc)."
      echo "--- recent log ($SERVICE_LOG) ---"
      tail -n 30 "$SERVICE_LOG" 2>/dev/null || echo "(no log available)"
    } >&2
  fi
  exit $rc
}
trap on_exit EXIT

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

# Readiness must test the HTTP status code, not merely that something
# answered. While llama.cpp is loading a model its /health returns
#     503 {"error":{"message":"Loading model",...}}
# and a bare `curl -s -o /dev/null` succeeds on that, which would declare a
# 17 GB model ready seconds after launch and start the app server against a
# server that cannot yet serve it.
http_status() {
  local code
  # curl already prints 000 when it cannot connect, and *also* exits non-zero.
  # An `|| echo 000` here would therefore append a second one, yielding
  # "000000", which matches no expected case and was misread as "loading" --
  # making a start against a dead server wait instead of failing. Capture the
  # output and let a non-zero exit pass.
  code="$(curl -s -o /dev/null -m "${2:-3}" -w '%{http_code}' "$1" 2>/dev/null || true)"
  [[ -z "$code" ]] && code="000"        # curl missing entirely
  printf '%s' "$code"
}

# Echoes: ready | loading | down
llama_state() {
  local code
  code="$(http_status "http://$LLAMA_HOST:$LLAMA_PORT/health")"
  case "$code" in
    200) echo "ready"; return ;;
    503) echo "loading"; return ;;
    000|"") ;;                       # nothing listening; fall through to /props
    *) echo "loading"; return ;;     # listening but unhappy: not ready yet
  esac
  code="$(http_status "http://$LLAMA_HOST:$LLAMA_PORT/props")"
  case "$code" in
    200) echo "ready" ;;
    000|"") echo "down" ;;
    *) echo "loading" ;;
  esac
}

llama_ready() {
  [[ "$(llama_state)" == "ready" ]]
}

app_ready() {
  [[ "$(http_status "http://$APP_HOST:$APP_PORT/v1/models")" == "200" ]]
}

code_fingerprint() {
  cat "$PROJECT_DIR/app/review_pipeline.py" "$PROJECT_DIR/app/server.py" \
      "$PROJECT_DIR/app/llm_backend.py" 2>/dev/null \
    | shasum -a 1 2>/dev/null | cut -c1-12
}

warn_if_code_changed() {
  # Called when the app server is already running. Compares the code the
  # running process imported against what is on disk now.
  local recorded current
  [[ -f "$CODE_FINGERPRINT_FILE" ]] || return 0
  recorded="$(cat "$CODE_FINGERPRINT_FILE" 2>/dev/null)"
  current="$(code_fingerprint)"
  [[ -z "$current" || "$recorded" == "$current" ]] && return 0
  log_line ""
  log_line "=============================================================="
  log_line "The app server that is already running was started from a"
  log_line "DIFFERENT version of the code ($recorded, now $current)."
  log_line "It imported review_pipeline.py at start-up and will keep using"
  log_line "that version, so any change made since is NOT in effect."
  log_line ""
  log_line "  ./scripts/qwen_service.sh restart"
  log_line "=============================================================="
  log_line ""
  return 1
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

  local existing state
  existing="$(running_pid "$LLAMA_PID_FILE" "llama-server")"
  state="$(llama_state)"

  if [[ -n "$existing" ]]; then
    case "$state" in
      ready)
        log_line "llama-server already running (pid $existing)."
        return 0 ;;
      loading)
        log_line "llama-server (pid $existing) is still loading the model; waiting..."
        wait_for_llama "$existing" && return 0
        return 1 ;;
    esac
    # Alive but not answering at all: it is wedged. Leave it for the user.
    log_line "ERROR: llama-server (pid $existing) is running but not answering on port $LLAMA_PORT."
    log_line "       Run './scripts/qwen_service.sh stop' first, or check $LLAMA_LOG"
    return 1
  fi

  if [[ "$state" != "down" ]]; then
    log_line "Reusing the llama-server already on port $LLAMA_PORT (started elsewhere)."
    # Not ours, so do not record a pid: stop must not kill it.
    rm -f "$LLAMA_PID_FILE"
    [[ "$state" == "loading" ]] && { log_line "It is still loading; waiting..."; wait_for_llama "" || return 1; }
    return 0
  fi

  if port_in_use "$LLAMA_PORT"; then
    log_line "ERROR: port $LLAMA_PORT is held by pid $(port_owner "$LLAMA_PORT") but is not answering."
    log_line "       Refusing to kill an unknown process. Free the port or set LLAMA_SERVER_PORT."
    return 1
  fi

  # Vision needs a projector alongside the model. Upstream warns that Qwen-VL
  # models need at least 1024 image tokens to place things correctly on the
  # page, which is exactly what reading a table cell depends on.
  local -a vision_args=()
  if [[ "$QWEN_VISION_TABLES" == "1" ]]; then
    local mmproj
    mmproj="$(ls "$(dirname "$MODEL")"/*mmproj*.gguf 2>/dev/null | head -1)"
    if [[ -n "$mmproj" ]]; then
      vision_args=(--mmproj "$mmproj" --image-min-tokens 1024)
      log_line "Vision enabled: $(basename "$mmproj")"
    else
      log_line "WARNING: --vision was asked for but no mmproj file sits beside"
      log_line "         $(basename "$MODEL"). Starting without it; tables will"
      log_line "         be read from the text layer only."
      QWEN_VISION_TABLES=0
    fi
  fi

  log_line "Starting llama-server on port $LLAMA_PORT ($(basename "$MODEL"))..."
  nohup "$LLAMA_BIN" \
    --model "$MODEL" \
    --host "$LLAMA_HOST" \
    --port "$LLAMA_PORT" \
    --ctx-size "$LLAMA_CTX" \
    --n-gpu-layers "$LLAMA_NGL" \
    --jinja \
    "${vision_args[@]}" \
    >> "$LLAMA_LOG" 2>&1 < /dev/null &
  echo $! > "$LLAMA_PID_FILE"
  log_line "llama-server pid $(cat "$LLAMA_PID_FILE"), log: $LLAMA_LOG"

  [[ "$WAIT_FOR_READY" -eq 1 ]] || return 0
  wait_for_llama "$(cat "$LLAMA_PID_FILE")"
}

# Wait for llama-server to report a genuine 200. $1 is its pid, or empty when
# the server was started elsewhere and there is no pid to watch.
wait_for_llama() {
  local pid="${1:-}" deadline elapsed=0
  deadline=$(( $(date +%s) + STARTUP_TIMEOUT ))
  while [[ $(date +%s) -lt $deadline ]]; do
    case "$(llama_state)" in
      ready)
        log_line "llama-server ready (${elapsed}s)."
        return 0 ;;
      down)
        if [[ -n "$pid" ]] && ! pid_is_alive "$pid"; then
          log_line "ERROR: llama-server exited during startup. Last lines:"
          tail -n 20 "$LLAMA_LOG" 2>/dev/null | while IFS= read -r l; do log_line "  $l"; done
          rm -f "$LLAMA_PID_FILE"
          return 1
        fi ;;
    esac
    if [[ -n "$pid" ]] && ! pid_is_alive "$pid"; then
      log_line "ERROR: llama-server exited during startup. Last lines:"
      tail -n 20 "$LLAMA_LOG" 2>/dev/null | while IFS= read -r l; do log_line "  $l"; done
      rm -f "$LLAMA_PID_FILE"
      return 1
    fi
    # A 17 GB model can take a while; say something every 30s.
    if [[ $(( elapsed % 30 )) -eq 0 && $elapsed -gt 0 ]]; then
      log_line "  still loading (${elapsed}s)..."
    fi
    sleep 2
    elapsed=$(( elapsed + 2 ))
  done
  log_line "ERROR: llama-server did not become ready within ${STARTUP_TIMEOUT}s."
  log_line "       Raise it with QWEN_STARTUP_TIMEOUT, or check $LLAMA_LOG"
  return 1
}

start_app() {
  local existing
  existing="$(running_pid "$APP_PID_FILE" "server.py")"
  if [[ -n "$existing" ]]; then
    log_line "App server already running (pid $existing)."
    if ! warn_if_code_changed; then
      return 1
    fi
    return 0
  fi

  if port_in_use "$APP_PORT"; then
    log_line "ERROR: port $APP_PORT is already in use by pid $(port_owner "$APP_PORT")."
    log_line "       Refusing to kill it. Stop it yourself or set QWEN_APP_PORT."
    return 1
  fi

  log_line "Starting the app server on port $APP_PORT ($REVIEW_PASSES synthesis pass(es), reasoning effort: ${LLAMA_REASONING_EFFORT:-medium (default)}, vision: $([[ "$QWEN_VISION_TABLES" == "1" ]] && echo on || echo off))..."
  cd "$PROJECT_DIR" || return 1

  QWEN_LLM_BACKEND="$([[ "$MODEL" == *.gguf ]] && echo llama-server || echo mlx)" \
  LLAMA_SERVER_URL="http://$LLAMA_HOST:$LLAMA_PORT" \
  REVIEW_PASSES="$REVIEW_PASSES" \
  LLAMA_REASONING_EFFORT="$LLAMA_REASONING_EFFORT" \
  QWEN_VISION_TABLES="$QWEN_VISION_TABLES" \
  nohup "$VENV_PYTHON" "$APP_PY" \
    --model "$MODEL" \
    --host "$APP_HOST" \
    --port "$APP_PORT" \
    >> "$APP_LOG" 2>&1 < /dev/null &
  echo $! > "$APP_PID_FILE"
  code_fingerprint > "$CODE_FINGERPRINT_FILE" 2>/dev/null || true
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

  local lstate
  lstate="$(llama_state)"
  if [[ -n "$llama_pid" ]]; then
    echo "llama-server: running (pid $llama_pid, port $LLAMA_PORT)"
  elif [[ "$lstate" != "down" ]]; then
    echo "llama-server: running on port $LLAMA_PORT, started elsewhere"
  else
    echo "llama-server: stopped"
  fi
  case "$lstate" in
    ready)   echo "  state:      ready" ;;
    loading) echo "  state:      loading the model (not yet accepting requests)" ;;
    down)    echo "  state:      not responding" ;;
  esac

  if [[ -n "$app_pid" ]]; then
    echo "app server:   running (pid $app_pid, port $APP_PORT)"
    if [[ -f "$CODE_FINGERPRINT_FILE" ]]; then
      local recorded current
      recorded="$(cat "$CODE_FINGERPRINT_FILE" 2>/dev/null)"
      current="$(code_fingerprint)"
      if [[ -n "$current" && "$recorded" != "$current" ]]; then
        echo "  code:       STALE - started from $recorded, disk is now $current"
        echo "              run 'restart' or your edits are not in effect"
      else
        echo "  code:       current ($current)"
      fi
    fi
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
    llama)   tail -n 40 -f "$LLAMA_LOG" ;;
    service) tail -n 40 -f "$SERVICE_LOG" ;;
    app|*)   tail -n 40 -f "$APP_LOG" ;;
  esac
}

# --- Doctor ----------------------------------------------------------------
# Reports the environment as this script sees it. Run it from Terminal and
# from an Automator action: a difference between the two is almost always the
# cause of "works in Terminal, fails in Automator".
cmd_doctor() {
  local problems=0
  local mark

  echo "Qwen review — environment report"
  echo "================================"
  echo "Invoked      : $([[ -t 1 ]] && echo 'interactive terminal' || echo 'non-interactive (Automator, launchd, cron)')"
  echo "Project      : $PROJECT_DIR"
  echo "User         : $(id -un)"
  echo "Shell        : ${SHELL:-unset}"
  echo ""
  echo "PATH:"
  echo "$PATH" | tr ':' '\n' | sed 's/^/  /'
  echo ""

  echo "Executables"
  echo "-----------"
  for tool in "$LLAMA_BIN" curl lsof open osascript; do
    if command -v "$tool" >/dev/null 2>&1; then
      printf "  ok    %-14s %s\n" "$tool" "$(command -v "$tool")"
    else
      printf "  MISS  %-14s not found on PATH\n" "$tool"
      [[ "$tool" == "$LLAMA_BIN" ]] && problems=1
    fi
  done
  echo ""

  echo "Python environment"
  echo "------------------"
  if [[ -x "$VENV_PYTHON" ]]; then
    printf "  ok    venv python   %s\n" "$("$VENV_PYTHON" -V 2>&1)"
    for module in fastapi uvicorn; do
      if "$VENV_PYTHON" -c "import $module" 2>/dev/null; then
        printf "  ok    %-14s importable\n" "$module"
      else
        printf "  MISS  %-14s not installed in the venv\n" "$module"
        problems=1
      fi
    done
  else
    printf "  MISS  venv python   %s does not exist\n" "$VENV_PYTHON"
    problems=1
  fi
  echo ""

  echo "Model"
  echo "-----"
  if [[ "$MODEL" == *.gguf ]]; then
    if [[ -f "$MODEL" ]]; then
      printf "  ok    %s (%s)\n" "$(basename "$MODEL")" "$(du -h "$MODEL" 2>/dev/null | cut -f1)"
    else
      printf "  MISS  %s\n" "$MODEL"
      problems=1
    fi
  else
    printf "  info  MLX model: %s (no llama-server needed)\n" "$MODEL"
  fi
  echo ""

  echo "Ports"
  echo "-----"
  for spec in "llama-server:$LLAMA_PORT" "app server:$APP_PORT"; do
    local label="${spec%:*}" port="${spec##*:}"
    if port_in_use "$port"; then
      printf "  busy  %-13s port %s held by pid %s (%s)\n" "$label" "$port" \
        "$(port_owner "$port")" \
        "$(ps -p "$(port_owner "$port")" -o comm= 2>/dev/null || echo unknown)"
    else
      printf "  free  %-13s port %s\n" "$label" "$port"
    fi
  done
  echo ""

  echo "Writable paths"
  echo "--------------"
  for dir in "$RUN_DIR" "$LOG_DIR"; do
    if [[ -w "$dir" ]]; then
      printf "  ok    %s\n" "$dir"
    else
      printf "  MISS  %s is not writable\n" "$dir"
      problems=1
    fi
  done
  echo ""

  if [[ $problems -eq 0 ]]; then
    mark="No problems found. 'start' should work from here."
  else
    mark="Problems found above — fix the MISS lines before starting."
  fi
  echo "$mark"
  return $problems
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
    --passes)  REVIEW_PASSES="$2"; shift 2 ;;
    --effort)  LLAMA_REASONING_EFFORT="$2"; shift 2 ;;
    --vision)  QWEN_VISION_TABLES=1; shift ;;
    llama|app|service) LOG_TARGET="$1"; shift ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

case "$COMMAND" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  restart) cmd_stop; sleep 2; cmd_start ;;
  status)  cmd_status ;;
  doctor|check) cmd_doctor ;;
  logs)    cmd_logs "${LOG_TARGET:-app}" ;;
  -h|--help|help)
    sed -n '2,30p' "$0"
    ;;
  *)
    echo "Unknown command: $COMMAND" >&2
    echo "Use: start | stop | restart | status | doctor | logs" >&2
    exit 1
    ;;
esac
