#!/bin/bash
SCRIPT_DIR="/Users/tonymyers/local-llm/qwen35-review"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/app/review_pipeline.py" "$@"
