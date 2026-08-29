#!/usr/bin/env python3
"""
Unified local server for chat and manuscript review.

Loads the MLX model once and exposes:
  - GET  /                       → serves the web UI
  - POST /v1/chat/completions    → OpenAI-compatible chat
  - POST /api/review             → file upload → review pipeline
  - GET  /api/review/status/{id} → SSE progress stream
  - GET  /v1/models              → model info (for status dot)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.responses import StreamingResponse

import uvicorn

# ---------------------------------------------------------------------------
# Resolve the review pipeline (same directory or via --pipeline-dir)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import review_pipeline as rp  # noqa: E402
from mlx_lm import load, generate  # noqa: E402

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(title="Local Qwen Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
MODEL_NAME = os.environ.get("MODEL_NAME", rp.MODEL_NAME)
model = None
tokenizer = None
model_lock = threading.Lock()

# In-flight review jobs: job_id → {status, progress, report, error}
review_jobs: dict = {}

HTML_PATH = SCRIPT_DIR / "chat.html"


def ensure_model():
    """Load the model if not yet loaded."""
    global model, tokenizer
    if model is None:
        print(f"Loading model: {MODEL_NAME}")
        model, tokenizer = load(MODEL_NAME)
        rp.MODEL_NAME = MODEL_NAME
        print("Model loaded.")


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    ensure_model()


# ---------------------------------------------------------------------------
# Serve the web UI
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    if HTML_PATH.exists():
        return HTMLResponse(HTML_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>chat.html not found</h1><p>Place chat.html next to server.py</p>")


# ---------------------------------------------------------------------------
# GET /v1/models — for the status dot
# ---------------------------------------------------------------------------
@app.get("/v1/models")
async def list_models():
    return {"data": [{"id": MODEL_NAME, "object": "model"}]}


# ---------------------------------------------------------------------------
# POST /v1/chat/completions — OpenAI-compatible chat
# ---------------------------------------------------------------------------
@app.post("/v1/chat/completions")
async def chat_completions(request: dict):
    ensure_model()

    messages = request.get("messages", [])
    max_tokens = request.get("max_tokens", 1200)
    temperature = request.get("temperature", rp.TEMPERATURE)
    top_p = request.get("top_p", rp.TOP_P)

    # Build prompt from messages
    if getattr(tokenizer, "chat_template", None) is not None:
        try:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
    else:
        prompt = messages[-1]["content"] if messages else ""

    from mlx_lm.sample_utils import make_sampler
    sampler = make_sampler(temperature, top_p=top_p, top_k=rp.TOP_K)

    with model_lock:
        output = generate(
            model, tokenizer, prompt=prompt,
            max_tokens=max_tokens, sampler=sampler, verbose=False,
        )

    output = rp.clean_model_output(output)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "model": MODEL_NAME,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": output},
            "finish_reason": "stop",
        }],
    }


# ---------------------------------------------------------------------------
# POST /api/review — file upload, runs pipeline in background
# ---------------------------------------------------------------------------
@app.post("/api/review")
async def start_review(
    file: UploadFile = File(...),
    domain: str = Form("general"),
):
    # Save uploaded file to temp directory
    job_id = uuid.uuid4().hex[:12]
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"review_{job_id}_"))
    file_path = tmp_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    review_jobs[job_id] = {
        "status": "running",
        "progress": [],
        "report": None,
        "appendix": None,
        "error": None,
        "filename": file.filename,
    }

    # Run review in background thread
    thread = threading.Thread(
        target=_run_review, args=(job_id, file_path, domain, tmp_dir),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "running"}


def _add_progress(job_id: str, message: str):
    """Thread-safe progress append."""
    if job_id in review_jobs:
        review_jobs[job_id]["progress"].append(message)


def _build_appendix_text(
    file_path: Path,
    manifest,
    table_blocks,
    chunks,
) -> str:
    """Build the evidence appendix as a markdown string (no file I/O)."""
    from datetime import datetime

    lines = []
    lines.append("# Evidence appendix")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"Model: {MODEL_NAME}")
    lines.append("")
    lines.append(f"## Input files\n- {file_path.name}")
    lines.append("")

    # Manifest summary
    lines.append("## Evidence manifest")
    lines.append("")
    lines.append(f"### {manifest.source_name}")
    lines.append("")
    lines.append("```text")
    lines.append(manifest.summary_text())
    lines.append("")
    lines.append("Detected model/result blocks:")
    lines.append(manifest.model_block_summary())
    lines.append("```")
    lines.append("")

    # Block type breakdown
    type_groups = {}
    for b in manifest.blocks:
        preview = b.text[:120].replace("\n", " ") + ("..." if len(b.text) > 120 else "")
        if b.model_method_class:
            preview = f"[{b.model_method_class.value}] {preview}"
        type_groups.setdefault(b.block_type.name, []).append(preview)

    for btype, previews in type_groups.items():
        lines.append(f"**{btype}** ({len(previews)} blocks)")
        lines.append("")
        for prev in previews[:5]:
            lines.append(f"- {prev}")
        if len(previews) > 5:
            lines.append(f"- ... and {len(previews) - 5} more")
        lines.append("")

    # Tables
    lines.append(f"## Extracted tables ({file_path.name})")
    lines.append("")
    if table_blocks:
        for page_num, block in table_blocks:
            lines.append(f"### Page {page_num}")
            lines.append("")
            lines.append("```text\n" + block + "\n```")
            lines.append("")
    else:
        manifest_tables = [b for b in manifest.blocks if b.block_type.name == "TABLE"]
        if manifest_tables:
            lines.append(
                f"No structured tables from PDF parser. "
                f"{len(manifest_tables)} inline table(s) recovered (shown in manifest above)."
            )
        else:
            lines.append("No extracted table blocks recorded.")
    lines.append("")

    # Chunk previews
    max_preview = 1800
    lines.append("## Chunk previews")
    lines.append("")
    for i, chunk_text in enumerate(chunks, start=1):
        preview = chunk_text[:max_preview]
        if len(chunk_text) > max_preview:
            preview += "\n...[truncated]..."
        lines.append(f"### Chunk {i}")
        lines.append("")
        lines.append("```text\n" + preview + "\n```")
        lines.append("")

    return "\n".join(lines)


def _run_review(job_id: str, file_path: Path, domain: str, tmp_dir: Path):
    """Run the full review pipeline (called in background thread)."""
    ensure_model()

    try:
        _add_progress(job_id, f"Reading {file_path.name}...")
        text, table_blocks = rp.load_document(file_path)

        _add_progress(job_id, "Structuring evidence...")
        manifest = rp.structure_evidence(file_path.name, text, table_blocks)
        mc = manifest.method_class
        _add_progress(job_id, f"Method: {mc.value}")
        if manifest.additional_method_classes:
            extra = ", ".join(m.value for m in manifest.additional_method_classes)
            _add_progress(job_id, f"Additional methods: {extra}")

        method_expectations = rp.get_method_expectations(
            mc, additional_classes=manifest.additional_method_classes,
        )
        manifest_summary = manifest.summary_text()

        chunks = rp.split_text(text)
        if not chunks:
            review_jobs[job_id]["status"] = "error"
            review_jobs[job_id]["error"] = "No usable text extracted."
            return

        # Chunk review
        chunk_outputs = []
        for i, chunk_text in enumerate(chunks, start=1):
            _add_progress(job_id, f"Reviewing chunk {i}/{len(chunks)}...")
            chunk = rp.DocChunk(source_name=file_path.name, chunk_id=i, text=chunk_text)
            with model_lock:
                reviewed = rp.review_chunk(
                    model, tokenizer, chunk,
                    method_expectations=method_expectations,
                    manifest_summary=manifest_summary,
                )
            chunk_outputs.append(reviewed)

        combined = "\n\n".join(
            f"### Chunk {i}\n{txt}" for i, txt in enumerate(chunk_outputs, start=1)
        )

        # File-level synthesis
        _add_progress(job_id, "Synthesising file-level review...")
        with model_lock:
            file_summary = rp.synthesize_file_review(
                model, tokenizer, file_path.name, combined,
                method_expectations=method_expectations,
                manifest_summary=manifest_summary,
            )

        file_summaries = [(file_path.name, file_summary)]
        all_manifests = [manifest]

        # Final synthesis
        _add_progress(job_id, "Synthesising final report...")
        with model_lock:
            final_report = rp.synthesize_report(
                model, tokenizer, file_summaries, all_manifests=all_manifests,
            )

        # Programmatic post-checks
        all_corrections = rp.programmatic_post_checks(final_report, manifest)
        if all_corrections:
            _add_progress(job_id, f"Applying {len(all_corrections)} programmatic correction(s)...")

        # LLM validation
        _add_progress(job_id, "Validating report against evidence...")
        with model_lock:
            final_report = rp.validate_report_against_evidence(
                model, tokenizer, final_report, file_summaries,
                programmatic_corrections=all_corrections if all_corrections else None,
            )

        # Post-processing passes
        _add_progress(job_id, "Post-processing...")
        all_text = "\n\n".join(t for _, t in file_summaries)
        all_tables = [tbl for _, tbl in table_blocks]

        final_report = rp.correct_review_contradictions(final_report, all_text, all_tables)
        final_report = rp.correct_direction_of_effect_summaries(final_report, all_text, all_tables)
        final_report = rp.apply_method_sensitive_critique_rules(final_report, all_manifests)
        final_report = rp.enforce_negative_constraints(final_report)
        final_report = rp.clean_markdown_math_artifacts(final_report)

        # Add header
        from datetime import datetime
        header = (
            f"# Local peer-review report\n\n"
            f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Model: {MODEL_NAME}\n\n"
            f"Input files:\n- {file_path.name}\n\n"
            f"Evidence summary:\n"
            f"- **{file_path.name}**: method={mc.value}, "
            f"tables={manifest.n_tables}, "
            f"model_spec={manifest.has_model_spec}, "
            f"equations={manifest.has_equations}, "
            f"SEs={manifest.has_standard_errors}, "
            f"variance_components={manifest.has_variance_components}, "
            f"fit_stats={manifest.has_model_fit_stats}\n\n---\n\n"
        )
        final_report = header + final_report

        # --- Generate evidence appendix (in-memory, not written to disk) ---
        _add_progress(job_id, "Generating evidence appendix...")
        appendix_lines = _build_appendix_text(
            file_path, manifest, table_blocks, chunks,
        )

        review_jobs[job_id]["report"] = final_report
        review_jobs[job_id]["appendix"] = appendix_lines
        review_jobs[job_id]["status"] = "complete"
        _add_progress(job_id, "Review complete.")

    except Exception as e:
        review_jobs[job_id]["status"] = "error"
        review_jobs[job_id]["error"] = f"{e}\n{traceback.format_exc()}"
        _add_progress(job_id, f"Error: {e}")

    finally:
        # Clean up temp files
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# GET /api/review/status/{job_id} — SSE progress stream
# ---------------------------------------------------------------------------
@app.get("/api/review/status/{job_id}")
async def review_status(job_id: str):
    if job_id not in review_jobs:
        return JSONResponse({"error": "Unknown job"}, status_code=404)

    async def event_stream():
        seen = 0
        while True:
            job = review_jobs.get(job_id)
            if not job:
                break

            # Send any new progress messages
            progress = job["progress"]
            while seen < len(progress):
                data = json.dumps({"type": "progress", "message": progress[seen]})
                yield f"data: {data}\n\n"
                seen += 1

            if job["status"] == "complete":
                data = json.dumps({
                    "type": "complete",
                    "report": job["report"],
                    "has_appendix": bool(job.get("appendix")),
                })
                yield f"data: {data}\n\n"
                break
            elif job["status"] == "error":
                data = json.dumps({"type": "error", "message": job.get("error", "Unknown error")})
                yield f"data: {data}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# GET /api/review/report/{job_id} — download report as markdown
# ---------------------------------------------------------------------------
@app.get("/api/review/report/{job_id}")
async def download_report(job_id: str):
    job = review_jobs.get(job_id)
    if not job or not job.get("report"):
        return JSONResponse({"error": "Report not ready"}, status_code=404)

    filename = job.get("filename", "document").rsplit(".", 1)[0]
    return JSONResponse(
        content={"report": job["report"], "filename": f"{filename}_review.md"},
    )


# ---------------------------------------------------------------------------
# GET /api/review/appendix/{job_id} — download evidence appendix
# ---------------------------------------------------------------------------
@app.get("/api/review/appendix/{job_id}")
async def download_appendix(job_id: str):
    job = review_jobs.get(job_id)
    if not job or not job.get("appendix"):
        return JSONResponse({"error": "Appendix not ready"}, status_code=404)

    return JSONResponse(content={"appendix": job["appendix"]})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Local Qwen chat + review server")
    parser.add_argument("--model", default=MODEL_NAME, help="MLX model name")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    args = parser.parse_args()

    MODEL_NAME = args.model
    rp.MODEL_NAME = args.model

    uvicorn.run(app, host=args.host, port=args.port)
