#!/bin/bash
# Start the local Qwen server and open the chat page in the browser.
#
# Usage:
#   ./start_chat_server.sh                          # defaults
#   ./start_chat_server.sh --port 9090              # custom port
#   ./start_chat_server.sh --model other/model-4bit # different model

# Resolve the project root from this script's own location, so the
# folder can be renamed or moved without editing anything.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_MODEL="mlx-community/Qwen3.6-35B-A3B-4bit"
DEFAULT_PORT=8080

# Parse arguments
MODEL="$DEFAULT_MODEL"
PORT="$DEFAULT_PORT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --port)  PORT="$2";  shift 2 ;;
    *)       echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Activate environment
source "$SCRIPT_DIR/.venv/bin/activate"

echo "Starting mlx_lm server..."
echo "  Model: $MODEL"
echo "  Port:  $PORT"
echo ""
echo "Chat page: file://$SCRIPT_DIR/chat.html"
echo "  (set server URL to http://localhost:$PORT in the toolbar)"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

# Open the chat page in the default browser
open "$SCRIPT_DIR/chat.html" 2>/dev/null || true

# Start the server (blocks until Ctrl+C)
python -m mlx_lm.server \
  --model "$MODEL" \
  --port "$PORT"
