#!/bin/bash
# Start the unified Qwen server (chat + review) and open the web UI.
#
# The default model is now the Qwen3.8-27B GGUF, served by llama.cpp's
# llama-server. This script will start llama-server for you if it is not
# already running, then start the FastAPI app that talks to it.
#
# The previous MLX models are unchanged and still selectable, e.g.
#   ./start_server.sh --model 35b

SCRIPT_DIR="/Users/tonymyers/local-llm/qwen35-review"
APP_DIR="$SCRIPT_DIR/app"
DEFAULT_PORT=8080
DEFAULT_HOST="127.0.0.1"

# --- Models ---------------------------------------------------------------
HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
QWEN38_27B_GGUF="$HF_HUB/models--unsloth--Qwen3.8-27B-GGUF/snapshots/4ca720788d1e01f1bff70c033e0d0028fd02e502/Qwen3.8-27B-UD-Q4_K_XL.gguf"

QWEN35_4BIT="mlx-community/Qwen3.6-35B-A3B-4bit"
QWEN27_6BIT="mlx-community/Qwen3.6-27B-6bit"
GEMMA4_26B_A4B_IT_4BIT="mlx-community/gemma-4-26b-a4b-it-4bit"

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

resolve_model() {
  case "$1" in
    qwen38|27b-gguf|gguf|qwen38-27b)
      echo "$QWEN38_27B_GGUF"
      ;;
    35b|35b-4bit|qwen35)
      echo "$QWEN35_4BIT"
      ;;
    27b|27b-6bit|qwen27)
      echo "$QWEN27_6BIT"
      ;;
    gemma4|gemma4-26b|gemma4-26b-it)
      echo "$GEMMA4_26B_A4B_IT_4BIT"
      ;;
    *)
      if [[ "$1" == */* || "$1" == .* || "$1" == ~* ]]; then
        echo "$1"
      else
        echo "Unknown model alias: $1" >&2
        echo "Run ./start_server.sh --list-models for installed aliases." >&2
        return 1
      fi
      ;;
  esac
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

This model uses the qwen35 architecture, which needs a recent llama.cpp
build. If llama-server loads but reports an unknown architecture, upgrade it.

To use the previous MLX model instead:
  ./start_server.sh --model 35b
EOF
    exit 1
  fi

  if is_llama_up; then
    echo "Reusing the llama-server already listening on $LLAMA_URL"
  else
    mkdir -p "$SCRIPT_DIR/logs"
    echo "Starting llama-server on $LLAMA_URL (log: $LLAMA_LOG)"
    "$LLAMA_BIN" \
      --model "$MODEL" \
      --host "$LLAMA_HOST" \
      --port "$LLAMA_PORT" \
      --ctx-size "$LLAMA_CTX" \
      --n-gpu-layers "$LLAMA_NGL" \
      --jinja \
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
