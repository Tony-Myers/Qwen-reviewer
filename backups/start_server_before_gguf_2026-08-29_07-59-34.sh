#!/bin/bash
# Start the unified Qwen server (chat + review) and open the web UI.

SCRIPT_DIR="/Users/tonymyers/local-llm/qwen35-review"
APP_DIR="$SCRIPT_DIR/app"
DEFAULT_PORT=8080
DEFAULT_HOST="127.0.0.1"

QWEN35_4BIT="mlx-community/Qwen3.6-35B-A3B-4bit"
QWEN27_6BIT="mlx-community/Qwen3.6-27B-6bit"
GEMMA4_26B_A4B_IT_4BIT="mlx-community/gemma-4-26b-a4b-it-4bit"

DEFAULT_MODEL="$QWEN35_4BIT"
MODEL="$DEFAULT_MODEL"
PORT="$DEFAULT_PORT"
HOST="$DEFAULT_HOST"
OPEN_BROWSER=1

print_usage() {
  cat <<EOF
Local LLM Server

Usage:
  ./start_server.sh [options]

Options:
  --model MODEL       Model alias or Hugging Face repo ID.
  --port PORT         Server port (default: $DEFAULT_PORT).
  --host HOST         Bind address (default: $DEFAULT_HOST).
  --no-open           Do not open the browser after startup.
  --list-models       Show built-in model aliases.
  -h, --help          Show this help.

Examples:
  ./start_server.sh
  ./start_server.sh --port 8090
  ./start_server.sh --model 35b --port 8090
  ./start_server.sh --model 27b --port 8090
  ./start_server.sh --model gemma4 --port 8090
  ./start_server.sh --model mlx-community/other-downloaded-model --port 8090

Default:
  $DEFAULT_MODEL
EOF
}

list_models() {
  cat <<EOF
Installed model aliases:
  35b, 35b-4bit, qwen35       -> $QWEN35_4BIT
  27b, 27b-6bit, qwen27       -> $QWEN27_6BIT
  gemma4, gemma4-26b,
  gemma4-26b-it               -> $GEMMA4_26B_A4B_IT_4BIT

Full Hugging Face repo IDs are also accepted unchanged when you intentionally
want to load a model outside these installed aliases.
EOF
}

resolve_model() {
  case "$1" in
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

# Kill anything already on the port
lsof -ti:"$PORT" | xargs kill 2>/dev/null || true

source "$SCRIPT_DIR/.venv/bin/activate"

# Install FastAPI + uvicorn if not present
pip show fastapi > /dev/null 2>&1 || pip install fastapi uvicorn python-multipart

echo "============================================"
echo "  Local LLM Server"
echo "  Model: $MODEL"
echo "  Host:  $HOST"
echo "  Port:  $PORT"
echo "  UI:    http://localhost:$PORT"
echo "============================================"
echo ""
echo "Press Ctrl+C to stop."
echo ""

if [[ "$OPEN_BROWSER" -eq 1 ]]; then
  # Open browser after a delay to let the model load
  (sleep 8 && open "http://localhost:$PORT" 2>/dev/null) &
fi

python "$APP_DIR/server.py" --model "$MODEL" --port "$PORT" --host "$HOST"
