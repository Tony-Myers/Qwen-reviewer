#!/bin/bash
# Resolve the project root from this script's own location, so the
# folder can be renamed or moved without editing anything.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate"
python "$SCRIPT_DIR/app/review_pipeline.py" "$@"
