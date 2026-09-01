#!/usr/bin/env python3
"""
Unified local server for chat and manuscript review.

Loads the model once (llama.cpp for GGUF, mlx_lm for MLX repo ids) and exposes:
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
import subprocess
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
import llm_backend  # noqa: E402
from llm_backend import (  # noqa: E402
    BackendError,
    current_backend,
    generate,
    load,
    make_sampler,
    set_backend,
)

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
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
model = None
tokenizer = None
model_lock = threading.Lock()
restart_lock = threading.Lock()
restart_scheduled = False

# In-flight review jobs: job_id → {status, progress, report, error}
review_jobs: dict = {}

HTML_PATH = SCRIPT_DIR / "chat.html"
ROOT_DIR = SCRIPT_DIR.parent
LAUNCHER_PATH = ROOT_DIR / "start_server.sh"

MODEL_CHOICES = [
    {
        "id": "qwen38",
        "label": "Qwen3.8 27B UD-Q4_K_XL (GGUF)",
        "model": rp.QWEN38_27B_GGUF,
        "aliases": ["27b-gguf", "gguf", "qwen38-27b"],
    },
    {
        "id": "35b",
        "label": "Qwen3.6 35B-A3B 4-bit",
        "model": "mlx-community/Qwen3.6-35B-A3B-4bit",
        "aliases": ["35b-4bit", "qwen35"],
    },
    {
        "id": "27b",
        "label": "Qwen3.6 27B 6-bit",
        "model": "mlx-community/Qwen3.6-27B-6bit",
        "aliases": ["27b-6bit", "qwen27"],
    },
    {
        "id": "27b-4bit",
        "label": "Qwen3.6 27B 4-bit",
        "model": "mlx-community/Qwen3.6-27B-4bit",
        "aliases": [],
    },
    {
        "id": "27b-8bit",
        "label": "Qwen3.6 27B 8-bit",
        "model": "mlx-community/Qwen3.6-27B-8bit",
        "aliases": [],
    },
    {
        "id": "gemma4",
        "label": "Gemma 4 26B-A4B IT 4-bit",
        "model": "mlx-community/gemma-4-26b-a4b-it-4bit",
        "aliases": ["gemma4-26b", "gemma4-26b-it"],
    },
    {
        "id": "gemma4-31b",
        "label": "Gemma 4 31B IT 4-bit",
        "model": "mlx-community/gemma-4-31b-it-4bit",
        "aliases": ["gemma4-31b-it"],
    },
]

# Aliases from the UI model list, folded in on top of the canonical table in
# review_pipeline so that "35b" means the same thing here, on the command line
# and in the launcher.
MODEL_ALIAS_MAP = dict(rp.MODEL_ALIASES)
MODEL_ALIAS_MAP.update({
    key.lower(): choice["model"]
    for choice in MODEL_CHOICES
    for key in [choice["id"], *choice["aliases"]]
})


def _hf_cache_root() -> Path:
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"]).expanduser()
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]).expanduser() / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _cached_snapshot_for_model(model_id: str) -> Optional[Path]:
    """Return a complete local snapshot/file path for a model id, if present."""
    # A GGUF model is a single file, so an existence check is the whole test.
    if model_id.lower().endswith(".gguf"):
        gguf_path = Path(model_id).expanduser()
        return gguf_path if gguf_path.exists() else None

    if "/" not in model_id:
        local_path = Path(model_id).expanduser()
        return local_path if local_path.exists() else None

    repo_dir = _hf_cache_root() / f"models--{model_id.replace('/', '--')}"
    snapshots_dir = repo_dir / "snapshots"
    if not snapshots_dir.exists():
        return None

    for snapshot in sorted(snapshots_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not snapshot.is_dir():
            continue
        has_config = (snapshot / "config.json").exists()
        has_tokenizer = (snapshot / "tokenizer.json").exists() or (snapshot / "tokenizer_config.json").exists()
        index_path = snapshot / "model.safetensors.index.json"
        if index_path.exists():
            try:
                index_data = json.loads(index_path.read_text(encoding="utf-8"))
                weight_files = set(index_data.get("weight_map", {}).values())
                has_weights = bool(weight_files) and all((snapshot / name).exists() for name in weight_files)
            except Exception:
                has_weights = False
        else:
            has_weights = any(snapshot.glob("*.safetensors"))
        if has_config and has_tokenizer and has_weights:
            return snapshot
    return None


def installed_model_choices() -> list[dict]:
    """Return only built-in models that are fully cached locally."""
    choices = []
    for choice in MODEL_CHOICES:
        snapshot = _cached_snapshot_for_model(choice["model"])
        if snapshot is None:
            continue
        item = dict(choice)
        item["cached"] = True
        item["cache_path"] = str(snapshot)
        choices.append(item)

    if not any(choice["model"] == MODEL_NAME for choice in choices):
        snapshot = _cached_snapshot_for_model(MODEL_NAME)
        if snapshot is not None:
            choices.append({
                "id": MODEL_NAME,
                "label": MODEL_NAME,
                "model": MODEL_NAME,
                "aliases": [],
                "cached": True,
                "cache_path": str(snapshot),
            })

    return choices


def resolve_model_choice(value: str) -> str:
    """Resolve a launcher/UI alias to an MLX model id."""
    return MODEL_ALIAS_MAP.get(value.lower(), value)


def _is_valid_model_choice(value: str) -> bool:
    """Keep restart requests to simple aliases, repo ids, or local paths."""
    if not value or any(ch.isspace() for ch in value):
        return False
    if value.lower().endswith(".gguf"):
        return Path(value).expanduser().exists()
    return "/" in value or value.lower() in MODEL_ALIAS_MAP or value.startswith((".", "~"))


def ensure_model():
    """Load the model if not yet loaded."""
    global model, tokenizer
    if model is None:
        print(f"Loading model: {MODEL_NAME}")
        try:
            model, tokenizer = load(MODEL_NAME)
        except BackendError as exc:
            print("\n" + "=" * 60, file=sys.stderr)
            print("Could not load the model.", file=sys.stderr)
            print(exc, file=sys.stderr)
            print("=" * 60 + "\n", file=sys.stderr)
            raise
        rp.MODEL_NAME = MODEL_NAME
        print(f"Model loaded via the {current_backend()} backend.")


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
# GET /api/models/aliases — UI model switcher choices
# ---------------------------------------------------------------------------
@app.get("/api/models/aliases")
async def list_model_aliases():
    return {
        "current_model": MODEL_NAME,
        "models": installed_model_choices(),
    }


def _restart_after_response(model_choice: str):
    """Spawn the launcher with the requested model, then stop this process."""
    time.sleep(0.75)
    cmd = [
        str(LAUNCHER_PATH),
        "--model",
        model_choice,
        "--port",
        str(SERVER_PORT),
        "--host",
        SERVER_HOST,
        "--no-open",
    ]
    try:
        subprocess.Popen(
            cmd,
            cwd=str(ROOT_DIR),
            start_new_session=True,
        )
    except Exception:
        traceback.print_exc()
        return

    time.sleep(0.25)
    os._exit(0)


# ---------------------------------------------------------------------------
# POST /api/server/restart — controlled restart with a different model
# ---------------------------------------------------------------------------
@app.post("/api/server/restart")
async def restart_server(request: dict):
    global restart_scheduled

    model_choice = str(request.get("model") or "").strip()
    if not _is_valid_model_choice(model_choice):
        return JSONResponse({"error": "Invalid model choice"}, status_code=400)

    resolved_model = resolve_model_choice(model_choice)
    if _cached_snapshot_for_model(resolved_model) is None:
        return JSONResponse(
            {"error": "That model is not fully downloaded locally."},
            status_code=409,
        )

    if any(job.get("status") == "running" for job in review_jobs.values()):
        return JSONResponse(
            {"error": "A review is running. Wait for it to finish before switching models."},
            status_code=409,
        )

    if resolved_model == MODEL_NAME:
        return {
            "status": "unchanged",
            "model": resolved_model,
            "message": "That model is already loaded.",
        }

    with restart_lock:
        if restart_scheduled:
            return JSONResponse({"error": "A restart is already scheduled"}, status_code=409)
        restart_scheduled = True

    thread = threading.Thread(
        target=_restart_after_response,
        args=(model_choice,),
        daemon=True,
    )
    thread.start()

    return {
        "status": "restarting",
        "model": resolved_model,
    }


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

    # Inject default system prompt if no system message is present
    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        messages = [{"role": "system", "content": rp._DEFAULT_CHAT_SYSTEM}] + messages

    # Build prompt from messages
    if getattr(tokenizer, "chat_template", None) is not None:
        try:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=llm_backend.thinking_enabled(),
            )
        except TypeError:
            prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
    else:
        prompt = messages[-1]["content"] if messages else ""

    sampler = make_sampler(temperature, top_p=top_p, top_k=rp.TOP_K)

    with model_lock:
        output = generate(
            model, tokenizer, prompt=prompt,
            max_tokens=max_tokens, sampler=sampler, verbose=False,
        )

    output = rp.clean_model_output(output)
    output = rp.clean_markdown_math_artifacts(output)

    # Strip markdown heading markers (e.g. "### Title") — the chat UI
    # does not render markdown headings, so these appear as literal "#" chars.
    import re as _re
    output = _re.sub(r"^(#{1,6})\s+", "", output, flags=_re.MULTILINE)

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
    thinking: str = Form(""),
):
    # Save uploaded file to temp directory
    job_id = uuid.uuid4().hex[:12]
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"review_{job_id}_"))
    file_path = tmp_dir / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # "" leaves the process default alone; "1"/"0" force one mode for this
    # review only, so the two can be alternated over real use and compared.
    # "synthesis" is the hybrid: the eleven chunk notes, which are most of the
    # time and were never the weak stage, run in instruct, and only the
    # synthesis and validation think.
    choice = str(thinking).strip().lower()
    want_thinking = None
    thinking_scope = "review"
    if choice in ("1", "true", "on", "yes"):
        want_thinking = True
    elif choice in ("0", "false", "off", "no"):
        want_thinking = False
    elif choice in ("synthesis", "hybrid", "2"):
        want_thinking = True
        thinking_scope = "synthesis"

    review_jobs[job_id] = {
        "status": "running",
        "thinking": want_thinking,
        "thinking_scope": thinking_scope,
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
    lines.append(f"Model: {rp.model_display_name(MODEL_NAME)}")
    lines.append(f"Pipeline: {rp.PIPELINE_VERSION}")
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


def _reasoning_header_lines(scope: str = "review",
                            passes_note: str = "") -> str:
    """
    Two header lines: the mode that was requested, and what the model did.

    They can disagree. A server that rejects chat_template_kwargs, or a chat
    template that emits an empty <think></think> pair, produces a review headed
    "thinking" with no reasoning in it. Recording only the request makes that
    undetectable after the fact -- the same failure the pass count already had,
    fixed the same way, by counting rather than asserting.
    """
    requested = "thinking" if llm_backend.thinking_enabled() else "instruct"
    if requested == "thinking" and scope == "synthesis":
        requested = "thinking (synthesis and validation only)"
    stats = llm_backend.reasoning_stats()
    seen, total, chars = (stats["with_reasoning"], stats["generations"],
                          stats["chars"])

    if chars > 0:
        check = (f"reasoning emitted in {seen} of {total} generations "
                 f"({chars:,} characters)")
        if requested == "instruct":
            check += "; not requested, and removed from the report"
    elif requested.startswith("thinking"):
        check = (f"no reasoning emitted in any of {total} generations, so this "
                 f"run behaved as instruct")
    else:
        check = f"no reasoning emitted, as expected ({total} generations)"

    if stats.get("retries"):
        check += (f"; {stats['retries']} generation(s) were retried at a larger "
                  f"budget because the reasoning overran")
    if stats.get("fallbacks"):
        check += (f"; {stats['fallbacks']} were finished in instruct mode after "
                  f"the reasoning would not fit at all")
    if stats["template_kwargs_dropped"]:
        check += ("; the server rejected chat_template_kwargs, so the request "
                  "never reached the chat template")
    if passes_note:
        check += f"; {passes_note}"

    return f"Reasoning: {requested}\nReasoning check: {check}\n"


def _run_review(job_id: str, file_path: Path, domain: str, tmp_dir: Path):
    """Run the full review pipeline (called in background thread)."""
    ensure_model()

    # Held for the whole review, so every generation in it -- chunk notes, file
    # synthesis, the passes, validation -- runs in the same mode. Restored on
    # the way out even if the review fails.
    want_thinking = review_jobs.get(job_id, {}).get("thinking")
    # Counters are per review, so the header reports this run and not the last.
    llm_backend.reset_reasoning_stats()
    with llm_backend.thinking(want_thinking):
        _run_review_inner(job_id, file_path, domain, tmp_dir)


def _chunk_reasoning(job_id: str):
    """
    The mode the chunk notes run in.

    In the hybrid the outer setting is thinking, and the chunk loop steps back
    into instruct for the duration: the notes are eleven of the fourteen
    generations and most of the two hours, and they were never the stage that
    sourced its evidence badly.
    """
    scope = review_jobs.get(job_id, {}).get("thinking_scope", "review")
    return llm_backend.thinking(False if scope == "synthesis" else None)


def _run_review_inner(job_id: str, file_path: Path, domain: str, tmp_dir: Path):
    try:
        _add_progress(job_id, f"Reading {file_path.name}...")
        text, table_blocks = rp.load_document(file_path)

        _add_progress(job_id, "Structuring evidence...")
        derived = rp.detect_derived_input(text)
        if derived:
            raise ValueError(
                f"{file_path.name} looks like output from this pipeline rather "
                f"than a manuscript (found {', '.join(repr(d) for d in derived[:3])}). "
                "Reviewing a review produces a report that reads normally but "
                "describes the wrong document. Upload the original manuscript."
            )

        manifest = rp.structure_evidence(file_path.name, text, table_blocks)
        tables_text = rp.tables_for_prompt(table_blocks)
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
            with model_lock, _chunk_reasoning(job_id):
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
                tables_text=tables_text,
            )

        file_summaries = [(file_path.name, file_summary)]
        all_manifests = [manifest]

        # Final synthesis. Findings rotate between passes, so REVIEW_PASSES>1
        # runs the synthesis repeatedly and unions the concerns and checks.
        #
        # Each pass is validated on its own BEFORE the merge. Validating the
        # merged report instead cost the whole exercise: on one run the merge
        # contributed four items and validation removed four, a net gain of
        # nothing for three times the generation. Validation was written to
        # check a single coherent report against the evidence, so it is given
        # exactly that, and the union is taken of reports it has already
        # cleaned. Nothing is then dropped for having arrived late.
        passes = rp.REVIEW_PASSES
        passes_note = ""
        if review_jobs.get(job_id, {}).get("thinking") and passes > rp.THINKING_PASSES:
            passes_note = (f"passes reduced from {passes} to {rp.THINKING_PASSES} "
                           f"because reasoning repeats with every pass "
                           f"(QWEN_THINKING_PASSES to override)")
            _add_progress(job_id, passes_note[0].upper() + passes_note[1:])
            passes = rp.THINKING_PASSES
        drafts = []
        kept_total = [0, 0]
        raw_total = [0, 0]
        all_corrections = []
        for attempt in range(passes):
            label = f" (pass {attempt + 1} of {passes})" if passes > 1 else ""
            _add_progress(job_id, f"Synthesising final report{label}...")
            # The first pass stays at the standard low temperature and becomes
            # the base report; later passes are sampled warmer, or they would
            # largely repeat it and the union would add nothing.
            temperature = None if attempt == 0 else rp.REPEAT_PASS_TEMPERATURE
            print(f"[synthesis] pass {attempt + 1} of {passes} "
                  f"(temperature={temperature or rp.TEMPERATURE})", flush=True)
            with model_lock:
                draft = rp.synthesize_report(
                    model, tokenizer, file_summaries,
                    all_manifests=all_manifests,
                    tables_text=tables_text,
                    temperature=temperature,
                )

            corrections = rp.programmatic_post_checks(draft, manifest)
            all_corrections.extend(corrections)
            _add_progress(job_id, f"Validating report against evidence{label}...")
            before = rp.count_report_items(draft)
            with model_lock:
                draft = rp.validate_report_against_evidence(
                    model, tokenizer, draft, file_summaries,
                    programmatic_corrections=corrections if corrections else None,
                )
            after = rp.count_report_items(draft)
            for index in (0, 1):
                raw_total[index] += before[index]
                kept_total[index] += after[index]
            print(f"[validation] pass {attempt + 1}: concerns {before[0]} -> {after[0]}, "
                  f"checks {before[1]} -> {after[1]}", flush=True)
            drafts.append(draft)

        merge_stats = {}
        final_report = rp.merge_reports(drafts, stats=merge_stats)
        synthesis_note = (
            f"{merge_stats.get('passes', 1)} pass(es), each validated before merging; "
            f"validation kept {kept_total[0]}/{raw_total[0]} concerns and "
            f"{kept_total[1]}/{raw_total[1]} checks across passes; "
            f"{merge_stats.get('added', 0)} item(s) added to the base by later passes"
        )
        print(f"[synthesis] {synthesis_note}", flush=True)
        if passes > 1:
            _add_progress(job_id, f"Merged {passes} validated passes "
                                  f"({merge_stats.get('added', 0)} item(s) added).")

        # Post-processing passes
        _add_progress(job_id, "Post-processing...")
        all_text = "\n\n".join(t for _, t in file_summaries)
        all_tables = [tbl for _, tbl in table_blocks]

        # A safety net independent of cause. Every stage below handles an empty
        # string without complaint, so a review with nothing in it assembles
        # into a tidy report: a header, and a citation check reporting -- quite
        # accurately -- that it found no unverifiable quotations. One did. An
        # empty review is a failure and should arrive as one.
        if not final_report.strip():
            raise ValueError(
                "The model returned nothing for this paper, so there is no "
                "review to write. The app-server log holds the generations."
            )

        # Half a report is still valid markdown, and reads as though it were
        # meant to end where it does. It should arrive as a failure instead.
        cut_short = rp.report_looks_truncated(final_report)
        if cut_short:
            raise ValueError(
                f"The synthesis is incomplete: {cut_short}. In thinking mode "
                f"this usually means the reasoning took the generation budget; "
                f"raise QWEN_THINKING_EXTRA_TOKENS or QWEN_SYNTHESIS_MAX_TOKENS "
                f"and run it again, or choose Instruct."
            )

        final_report = rp.correct_review_contradictions(final_report, all_text, all_tables)
        final_report = rp.correct_direction_of_effect_summaries(final_report, all_text, all_tables)
        final_report = rp.apply_method_sensitive_critique_rules(final_report, all_manifests)
        final_report = rp.enforce_negative_constraints(final_report)
        final_report = rp.clean_markdown_math_artifacts(final_report)

        # Mechanical citation check: quotations must be findable in the
        # manuscript, and evidence must not cite the pipeline's own summary.
        citation_source = text + "\n" + "\n".join(b for _, b in table_blocks)
        final_report = rp.annotate_concern_confidence(final_report, citation_source)
        report_problems = (rp.verify_report_citations(final_report, citation_source)
                           + rp.evidence_echo_problems(final_report)
                           + rp.overclaim_problems(final_report))
        # Both checks above read the quotation marks; strip only afterwards.
        final_report = rp.mark_unverified_quotations(final_report, citation_source)
        final_report = rp.report_reliability_banner(final_report) + final_report
        final_report += rp.format_action_list(final_report)
        final_report += rp.format_consistency_check(text, table_blocks)
        final_report += rp.format_citation_check(report_problems, final_report)

        # Add header
        from datetime import datetime
        header = (
            f"# Local peer-review report\n\n"
            f"Generated: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Model: {rp.model_display_name(MODEL_NAME)}\n"
            f"Pipeline: {rp.PIPELINE_VERSION}\n"
            # Recorded so reviews accumulated over real use can be grouped by
            # mode afterwards; without it the comparison is unrecoverable.
            + _reasoning_header_lines(
                review_jobs.get(job_id, {}).get("thinking_scope", "review"),
                passes_note)
            # Recorded so a run is never ambiguous about whether the extra
            # passes actually happened, and what they contributed.
            + (f"Synthesis: {synthesis_note}\n" if passes > 1 else "")
            + f"\n"
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
    parser.add_argument("--model", default=MODEL_NAME,
                        help="Path to a .gguf file, or an MLX repo id")
    parser.add_argument("--backend", choices=["llama-server", "llama-cpp", "mlx"],
                        default=None,
                        help="Force a backend (default: inferred from --model)")
    parser.add_argument("--llama-url", default=None,
                        help="Base URL of the llama-server instance")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    args = parser.parse_args()

    if args.llama_url:
        os.environ["LLAMA_SERVER_URL"] = args.llama_url
    if args.backend:
        set_backend(args.backend)

    MODEL_NAME = resolve_model_choice(args.model)
    rp.MODEL_NAME = MODEL_NAME
    SERVER_HOST = args.host
    SERVER_PORT = args.port

    uvicorn.run(app, host=args.host, port=args.port)
