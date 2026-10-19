#!/bin/bash
# Start the unified Qwen server (chat + review) and open the web UI.
#
# The default model is now the Qwen3.8-27B GGUF, served by llama.cpp's
# llama-server. This script will start llama-server for you if it is not
# already running, then start the FastAPI app that talks to it.
#
# The previous MLX models are unchanged and still selectable, e.g.
#   ./start_server.sh --model 35b

# Resolve the project root from this script's own location, so the
# folder can be renamed or moved without editing anything.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
DEFAULT_PORT=8080
DEFAULT_HOST="127.0.0.1"

# --- Local settings, then models ------------------------------------------
# local.env is sourced before anything is worked out, so a setting there
# survives a restart started from the browser: the app server re-launches this
# script, and whatever was exported in a shell is long gone. See
# local.env.example.
if [[ -f "$SCRIPT_DIR/local.env" ]]; then
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/local.env"
fi

# shellcheck disable=SC1091
source "$SCRIPT_DIR/scripts/model_aliases.sh"

DEFAULT_MODEL="$QWEN38_27B_GGUF"
MODEL="$DEFAULT_MODEL"
PORT="$DEFAULT_PORT"
HOST="$DEFAULT_HOST"
OPEN_BROWSER=1

# --- llama-server (used only for GGUF models) -----------------------------
LLAMA_PORT="${LLAMA_SERVER_PORT:-8081}"
LLAMA_HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"
LLAMA_CTX="${LLAMA_SERVER_CTX:-32768}"
LLAMA_NGL="${LLAMA_SERVER_NGL:-99}"
LLAMA_BIN="${LLAMA_SERVER_BIN:-llama-server}"
LLAMA_LOG="$SCRIPT_DIR/logs/llama-server.log"
KEEP_LLAMA=0

print_usage() {
  cat <<EOF
Local LLM Server

Usage:
  ./start_server.sh [options]

Options:
  --model MODEL       Model alias, .gguf path, or Hugging Face repo ID.
  --port PORT         FastAPI server port (default: $DEFAULT_PORT).
  --host HOST         Bind address (default: $DEFAULT_HOST).
  --llama-port PORT   llama-server port for GGUF models (default: $LLAMA_PORT).
  --ctx N             llama-server context size (default: $LLAMA_CTX).
  --keep-llama        Leave llama-server running after this script exits.
  --no-open           Do not open the browser after startup.
  --list-models       Show built-in model aliases.
  -h, --help          Show this help.

Examples:
  ./start_server.sh                          # Qwen3.8-27B GGUF (default)
  ./start_server.sh --port 8090
  ./start_server.sh --model 35b --port 8090  # back to the MLX 35B model
  ./start_server.sh --model gemma4
  ./start_server.sh --model /path/to/other.gguf

Default:
  $DEFAULT_MODEL
EOF
}

list_models() {
  cat <<EOF
Installed model aliases:
  qwen38, 27b-gguf, gguf      -> $QWEN38_27B_GGUF
                                 (llama.cpp / llama-server)
  35b, 35b-4bit, qwen35       -> $QWEN35_4BIT   (MLX)
  27b, 27b-6bit, qwen27       -> $QWEN27_6BIT   (MLX)
  gemma4, gemma4-26b,
  gemma4-26b-it               -> $GEMMA4_26B_A4B_IT_4BIT   (MLX)

A full Hugging Face repo ID or an absolute path to a .gguf file is also
accepted unchanged.
EOF
}


while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      if [[ -z "${2:-}" ]]; then
        echo "Missing value for --model" >&2
        exit 1
      fi
      MODEL="$(resolve_model "$2")" || exit 1
      shift 2
      ;;
    --port)
      if [[ -z "${2:-}" ]]; then
        echo "Missing value for --port" >&2
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    --host)
      if [[ -z "${2:-}" ]]; then
        echo "Missing value for --host" >&2
        exit 1
      fi
      HOST="$2"
      shift 2
      ;;
    --llama-port)
      if [[ -z "${2:-}" ]]; then
        echo "Missing value for --llama-port" >&2
        exit 1
      fi
      LLAMA_PORT="$2"
      shift 2
      ;;
    --ctx)
      if [[ -z "${2:-}" ]]; then
        echo "Missing value for --ctx" >&2
        exit 1
      fi
      LLAMA_CTX="$2"
      shift 2
      ;;
    --keep-llama)
      KEEP_LLAMA=1
      shift
      ;;
    --no-open)
      OPEN_BROWSER=0
      shift
      ;;
    --list-models)
      list_models
      exit 0
      ;;
    -h|--help)
      print_usage
      echo ""
      list_models
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Run ./start_server.sh --help for usage." >&2
      exit 1
      ;;
  esac
done

# Kill anything already on the FastAPI port (but never touch llama-server)
lsof -ti:"$PORT" | xargs kill 2>/dev/null || true

source "$SCRIPT_DIR/.venv/bin/activate"

# Install FastAPI + uvicorn if not present
pip show fastapi > /dev/null 2>&1 || pip install fastapi uvicorn python-multipart

# ---------------------------------------------------------------------------
# For a GGUF model, make sure llama-server is up before starting the app.
# ---------------------------------------------------------------------------
LLAMA_URL="http://$LLAMA_HOST:$LLAMA_PORT"
LLAMA_PID=""

is_llama_up() {
  curl -s -o /dev/null -m 2 "$LLAMA_URL/health" 2>/dev/null \
    || curl -s -o /dev/null -m 2 "$LLAMA_URL/props" 2>/dev/null
}

stop_llama() {
  if [[ -n "$LLAMA_PID" && "$KEEP_LLAMA" -eq 0 ]]; then
    echo ""
    echo "Stopping llama-server (pid $LLAMA_PID)..."
    kill "$LLAMA_PID" 2>/dev/null || true
  fi
}

# Which model does the llama-server on this port actually have loaded?
#
# Reusing a running server is normally what you want: the model stays resident
# between runs. But it was reused without checking which model it held, so
# switching model from the web UI restarted the app server with the new path
# while llama-server carried on serving the old one. The report header takes
# its Model line from the app server, so it named a model that had not written
# a word of the review. Any comparison between two GGUF models was silently
# invalid. Empty means the server did not say, and then reuse is reported as
# unverified rather than claimed as a match.
served_llama_model() {
  local raw=""
  raw="$(curl -s -m 3 "$LLAMA_URL/v1/models" 2>/dev/null \
         | tr ',' '\n' \
         | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
         | head -1)"
  if [[ -z "$raw" ]]; then
    raw="$(curl -s -m 3 "$LLAMA_URL/props" 2>/dev/null \
           | tr ',' '\n' \
           | sed -n 's/.*"model_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
           | head -1)"
  fi
  if [[ -n "$raw" ]]; then
    basename "$raw"
  fi
  return 0
}

# Stop an llama-server this script did not start, so a different model can be
# loaded. The pid file written by scripts/qwen_service.sh is preferred; the
# listening process is the fallback for a server started by hand.
stop_served_llama() {
  local pid_file="$SCRIPT_DIR/run/llama-server.pid" pid=""

  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && ! ps -p "$pid" -o command= 2>/dev/null | grep -q llama-server; then
      pid=""
    fi
  fi
  if [[ -z "$pid" ]] && command -v lsof > /dev/null 2>&1; then
    pid="$(lsof -ti "tcp:$LLAMA_PORT" -sTCP:LISTEN 2>/dev/null | head -1)"
  fi
  [[ -n "$pid" ]] || return 1

  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    is_llama_up || { rm -f "$pid_file"; return 0; }
    sleep 0.5
  done
  kill -9 "$pid" 2>/dev/null || true
  sleep 1
  if is_llama_up; then
    return 1
  fi
  rm -f "$pid_file"
  return 0
}

if [[ "$MODEL" == *.gguf ]]; then
  if [[ ! -f "$MODEL" ]]; then
    echo "Model file not found: $MODEL" >&2
    exit 1
  fi

  if ! command -v "$LLAMA_BIN" > /dev/null 2>&1; then
    cat >&2 <<EOF
llama-server was not found on PATH (looked for: $LLAMA_BIN).

Install or update llama.cpp, for example:
  brew install llama.cpp      # or: brew upgrade llama.cpp

Each model needs a build that knows its architecture: qwen35 for the 27B,
qwen4exp for Flash-Next. If llama-server loads but reports an unknown
architecture, the build does not have that model. Point LLAMA_SERVER_BIN at a
build that does, and put it in local.env so the setting survives a restart
started from the browser -- see local.env.example.

To use the previous MLX model instead, which needs no llama-server at all:
  ./start_server.sh --model 35b
EOF
    exit 1
  fi

  NEEDS_LLAMA_START=1
  if is_llama_up; then
    SERVED_MODEL="$(served_llama_model)"
    WANTED_MODEL="$(basename "$MODEL")"
    if [[ -z "$SERVED_MODEL" ]]; then
      echo "Reusing the llama-server already listening on $LLAMA_URL."
      echo "It did not report which model it has loaded, so that was not checked."
      NEEDS_LLAMA_START=0
    elif [[ "$SERVED_MODEL" == "$WANTED_MODEL" ]]; then
      echo "Reusing the llama-server already listening on $LLAMA_URL ($SERVED_MODEL)"
      NEEDS_LLAMA_START=0
    else
      echo "llama-server on $LLAMA_URL has $SERVED_MODEL loaded, but $WANTED_MODEL"
      echo "was asked for. Stopping it so the requested model can be loaded."
      if ! stop_served_llama; then
        cat >&2 <<EOF

Could not stop the llama-server on port $LLAMA_PORT. It is serving
$SERVED_MODEL, so a review started now would be written by that model
whatever this launcher was asked for.

Stop it yourself, then start again:
  ./scripts/qwen_service.sh stop
EOF
        exit 1
      fi
    fi
  fi

  if [[ "$NEEDS_LLAMA_START" -eq 1 ]]; then
    mkdir -p "$SCRIPT_DIR/logs"
    echo "Starting llama-server on $LLAMA_URL (log: $LLAMA_LOG)"

    # Vision needs the projector in memory, and the per-review selector in the
    # browser can only turn vision on if it is. scripts/qwen_service.sh loads
    # one whenever it sits beside the model; this launcher did not, so a
    # restart from the web UI silently lost vision. Set QWEN_LOAD_MMPROJ=0 to
    # keep it out.
    LLAMA_VISION_ARGS=()
    if [[ "${QWEN_LOAD_MMPROJ:-1}" == "1" ]]; then
      MMPROJ_FILE="$(ls "$(dirname "$MODEL")"/*mmproj*.gguf 2>/dev/null | head -1)"
      if [[ -n "$MMPROJ_FILE" ]]; then
        LLAMA_VISION_ARGS=(--mmproj "$MMPROJ_FILE" --image-min-tokens 1024)
        echo "Vision available: $(basename "$MMPROJ_FILE")"
      else
        echo "No projector beside this model, so vision is unavailable."
      fi
    fi

    # Flags this model needs, and flags this machine needs. The first travel
    # with the model so that choosing it in the browser brings them along;
    # local.env cannot make a setting conditional on the model chosen.
    LLAMA_MODEL_ARGS=( $(model_extra_args "$MODEL") )
    LLAMA_EXTRA_ARGS=( ${LLAMA_SERVER_EXTRA_ARGS:-} )
    if [[ ${#LLAMA_MODEL_ARGS[@]} -gt 0 || ${#LLAMA_EXTRA_ARGS[@]} -gt 0 ]]; then
      echo "Extra llama-server flags: ${LLAMA_MODEL_ARGS[*]-} ${LLAMA_EXTRA_ARGS[*]-}"
    fi

    "$LLAMA_BIN" \
      --model "$MODEL" \
      --host "$LLAMA_HOST" \
      --port "$LLAMA_PORT" \
      --ctx-size "$LLAMA_CTX" \
      --n-gpu-layers "$LLAMA_NGL" \
      --jinja \
      ${LLAMA_VISION_ARGS[@]+"${LLAMA_VISION_ARGS[@]}"} \
      ${LLAMA_MODEL_ARGS[@]+"${LLAMA_MODEL_ARGS[@]}"} \
      ${LLAMA_EXTRA_ARGS[@]+"${LLAMA_EXTRA_ARGS[@]}"} \
      > "$LLAMA_LOG" 2>&1 &
    LLAMA_PID=$!
    trap stop_llama EXIT INT TERM

    printf "Loading the model"
    for _ in $(seq 1 300); do
      if is_llama_up; then
        echo " ready."
        break
      fi
      if ! kill -0 "$LLAMA_PID" 2>/dev/null; then
        echo ""
        echo "llama-server exited during startup. Last lines of the log:" >&2
        tail -n 25 "$LLAMA_LOG" >&2
        exit 1
      fi
      printf "."
      sleep 2
    done

    if ! is_llama_up; then
      echo ""
      echo "llama-server did not become ready in time. See $LLAMA_LOG" >&2
      exit 1
    fi
  fi

  export LLAMA_SERVER_URL="$LLAMA_URL"
  export QWEN_LLM_BACKEND="llama-server"
  BACKEND_LABEL="llama.cpp @ $LLAMA_URL"
else
  export QWEN_LLM_BACKEND="mlx"
  BACKEND_LABEL="MLX (in-process)"
fi

echo "============================================"
echo "  Local LLM Server"
echo "  Model:   $(basename "$MODEL")"
echo "  Backend: $BACKEND_LABEL"
echo "  Host:    $HOST"
echo "  Port:    $PORT"
echo "  UI:      http://localhost:$PORT"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop."
echo ""

if [[ "$OPEN_BROWSER" -eq 1 ]]; then
  # Open browser after a short delay; the model is already loaded by now
  # when using llama-server, so this can be shorter than it used to be.
  (sleep 3 && open "http://localhost:$PORT" 2>/dev/null) &
fi

python "$APP_DIR/server.py" --model "$MODEL" --port "$PORT" --host "$HOST"
