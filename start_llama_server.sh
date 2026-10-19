#!/bin/bash
# Start llama.cpp's llama-server with the Qwen3.8-27B GGUF and leave it running.
#
# Useful when you want the model resident across several pipeline runs, or when
# running review_pipeline.py directly from the command line rather than through
# start_server.sh (which starts llama-server for you).
#
# Usage:
#   ./start_llama_server.sh              # foreground, Ctrl+C to stop
#   ./start_llama_server.sh --port 8081 --ctx 32768

HF_HUB="${HF_HUB_CACHE:-$HOME/.cache/huggingface/hub}"
MODEL="${LLAMA_MODEL:-$HF_HUB/models--unsloth--Qwen3.8-27B-GGUF/snapshots/4ca720788d1e01f1bff70c033e0d0028fd02e502/Qwen3.8-27B-UD-Q4_K_XL.gguf}"

HOST="${LLAMA_SERVER_HOST:-127.0.0.1}"
PORT="${LLAMA_SERVER_PORT:-8081}"
CTX="${LLAMA_SERVER_CTX:-32768}"
NGL="${LLAMA_SERVER_NGL:-99}"
BIN="${LLAMA_SERVER_BIN:-llama-server}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --host)  HOST="$2";  shift 2 ;;
    --port)  PORT="$2";  shift 2 ;;
    --ctx)   CTX="$2";   shift 2 ;;
    --ngl)   NGL="$2";   shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ ! -f "$MODEL" ]]; then
  echo "Model file not found: $MODEL" >&2
  exit 1
fi

if ! command -v "$BIN" > /dev/null 2>&1; then
  echo "llama-server not found on PATH (looked for: $BIN)." >&2
  echo "Install or update llama.cpp:  brew install llama.cpp" >&2
  exit 1
fi

echo "Model: $(basename "$MODEL")"
echo "URL:   http://$HOST:$PORT"
echo ""
echo "Point the pipeline at it with:"
echo "  export LLAMA_SERVER_URL=http://$HOST:$PORT"
echo ""

# --jinja is required: it makes llama.cpp apply the chat template embedded in
# the GGUF, which is what honours enable_thinking=false and suppresses the
# model's reasoning block.
exec "$BIN" \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --n-gpu-layers "$NGL" \
  --jinja
