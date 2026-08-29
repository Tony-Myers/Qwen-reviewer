#!/bin/bash
# Delegate to the repo-level launcher so model aliases stay in one place.

SCRIPT_DIR="/Users/tonymyers/local-llm/qwen35-review"
exec "$SCRIPT_DIR/start_server.sh" "$@"
