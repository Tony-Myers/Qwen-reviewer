#!/usr/bin/env python3
"""Regression checks for cooperative review cancellation."""

import asyncio
import inspect
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import server  # noqa: E402


failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        failures.append(label)


def response_payload(response):
    import json

    body = getattr(response, "body", b"")
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    return json.loads(body) if body else {}


print("\n[running review accepts a cancellation request]")

original_jobs = server.review_jobs
job_id = "cancel-running"

server.review_jobs = {
    job_id: {
        "status": "running",
        "thinking": None,
        "thinking_scope": "review",
        "vision": None,
        "progress": [],
        "report": None,
        "appendix": None,
        "error": None,
        "filename": "synthetic.txt",
    }
}

try:
    cancel_endpoint = getattr(server, "cancel_review", None)

    check(
        "cancellation endpoint exists",
        cancel_endpoint is not None,
        "server.cancel_review is missing",
    )

    if cancel_endpoint is not None:
        result = cancel_endpoint(job_id)
        if inspect.isawaitable(result):
            result = asyncio.run(result)

        payload = (
            response_payload(result)
            if hasattr(result, "body")
            else result
        )

        check(
            "running review accepts cancellation",
            payload.get("status") in {"cancelling", "cancelled"},
            repr(payload),
        )
        check(
            "job records cancellation request",
            bool(server.review_jobs[job_id].get("cancel_requested")),
            repr(server.review_jobs[job_id]),
        )

        again = cancel_endpoint(job_id)
        if inspect.isawaitable(again):
            again = asyncio.run(again)
        again_payload = (
            response_payload(again)
            if hasattr(again, "body")
            else again
        )

        check(
            "repeated cancellation is idempotent",
            again_payload.get("status") in {"cancelling", "cancelled"},
            repr(again_payload),
        )

finally:
    server.review_jobs = original_jobs


print("\n[cancelled review stops before its next chunk inference]")

source = inspect.getsource(server._run_review_inner)

check(
    "review worker contains an explicit cancellation checkpoint",
    "cancel" in source.lower(),
    "no cancellation check appears in _run_review_inner()",
)

check(
    "chunk loop checks cancellation before review_chunk",
    (
        "cancel" in source.lower()
        and source.lower().find("cancel") < source.find("rp.review_chunk(")
    ),
    "no cancellation checkpoint is visible before the first chunk generation",
)


print("\n[cancelled is represented as a terminal SSE state]")

status_source = inspect.getsource(server.review_status)

check(
    "status stream recognises cancelled reviews",
    '"cancelled"' in status_source or "'cancelled'" in status_source,
    "review_status() currently terminates only for complete/error",
)


print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    raise SystemExit(1)

print("PASS: cooperative review cancellation is represented in the server lifecycle")

print("\n[cancellation between chunks prevents further inference]")

original_jobs = server.review_jobs
original_load_document = server.rp.load_document
original_detect_derived_input = server.rp.detect_derived_input
original_structure_evidence = server.rp.structure_evidence
original_tables_for_prompt = server.rp.tables_for_prompt
original_get_method_expectations = server.rp.get_method_expectations
original_split_text = server.rp.split_text
original_review_chunk = server.rp.review_chunk

job_id = "cancel-between-chunks"
tmp_dir = Path(tempfile.mkdtemp(prefix="review_cancel_chunks_test_"))
file_path = tmp_dir / "upload.txt"
file_path.write_text("synthetic manuscript", encoding="utf-8")

server.review_jobs = {
    job_id: {
        "status": "running",
        "thinking": None,
        "thinking_scope": "review",
        "vision": None,
        "progress": [],
        "report": None,
        "appendix": None,
        "error": None,
        "filename": "synthetic.txt",
        "cancel_requested": False,
    }
}

review_calls = []


class FakeMethodClass:
    value = "synthetic"


class FakeManifest:
    method_class = FakeMethodClass()
    additional_method_classes = []
    design_class = None
    synthesis_method_class = None

    def summary_text(self):
        return "synthetic manifest"


def fake_load_document(path):
    return "synthetic manuscript text", [], []


def fake_detect_derived_input(text):
    return []


def fake_structure_evidence(filename, text, table_blocks):
    return FakeManifest()


def fake_tables_for_prompt(table_blocks):
    return ""


def fake_get_method_expectations(*args, **kwargs):
    return "synthetic expectations"


def fake_split_text(text):
    return ["first chunk", "second chunk"]


def fake_review_chunk(model, tokenizer, chunk, **kwargs):
    review_calls.append(chunk.chunk_id)
    if chunk.chunk_id == 1:
        server.review_jobs[job_id]["cancel_requested"] = True
    return f"reviewed chunk {chunk.chunk_id}"


server.rp.load_document = fake_load_document
server.rp.detect_derived_input = fake_detect_derived_input
server.rp.structure_evidence = fake_structure_evidence
server.rp.tables_for_prompt = fake_tables_for_prompt
server.rp.get_method_expectations = fake_get_method_expectations
server.rp.split_text = fake_split_text
server.rp.review_chunk = fake_review_chunk

try:
    server._run_review_inner(
        job_id,
        file_path,
        "general",
        tmp_dir,
    )

    job = server.review_jobs[job_id]

    check(
        "only the first chunk reaches inference",
        review_calls == [1],
        repr(review_calls),
    )
    check(
        "worker reaches cancelled terminal state",
        job.get("status") == "cancelled",
        f"status={job.get('status')!r}",
    )
    check(
        "cancellation is not recorded as an error",
        job.get("error") is None,
        repr(job.get("error")),
    )
    check(
        "cancellation is visible in progress",
        any(
            message == "Review cancelled."
            for message in job.get("progress", [])
        ),
        repr(job.get("progress")),
    )
    check(
        "cancelled review does not claim completion",
        not any(
            message == "Review complete."
            for message in job.get("progress", [])
        ),
        repr(job.get("progress")),
    )

finally:
    server.rp.load_document = original_load_document
    server.rp.detect_derived_input = original_detect_derived_input
    server.rp.structure_evidence = original_structure_evidence
    server.rp.tables_for_prompt = original_tables_for_prompt
    server.rp.get_method_expectations = original_get_method_expectations
    server.rp.split_text = original_split_text
    server.rp.review_chunk = original_review_chunk
    server.review_jobs = original_jobs

    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    raise SystemExit(1)

print("PASS: cancellation stops a review before its next inference")


print("\n[scheduler cancellation inside the real review pipeline is terminal cancellation]")

original_jobs = server.review_jobs
original_load_document = server.rp.load_document
original_detect_derived_input = server.rp.detect_derived_input
original_structure_evidence = server.rp.structure_evidence
original_tables_for_prompt = server.rp.tables_for_prompt
original_get_method_expectations = server.rp.get_method_expectations
original_split_text = server.rp.split_text
original_review_chunk = server.rp.review_chunk

job_id = "cancel-inside-real-pipeline"
tmp_dir = Path(tempfile.mkdtemp(prefix="review_cancel_inner_test_"))
file_path = tmp_dir / "upload.txt"
file_path.write_text("synthetic manuscript", encoding="utf-8")

server.review_jobs = {
    job_id: {
        "status": "running",
        "thinking": None,
        "thinking_scope": "review",
        "vision": None,
        "progress": [],
        "report": None,
        "appendix": None,
        "error": None,
        "filename": "synthetic.txt",
        "cancel_requested": True,
    }
}


def fake_cancelled_review_chunk(model, tokenizer, chunk, **kwargs):
    raise server.llm_backend.InferenceCancelledError(
        "Local model inference was cancelled while waiting."
    )


server.rp.load_document = fake_load_document
server.rp.detect_derived_input = fake_detect_derived_input
server.rp.structure_evidence = fake_structure_evidence
server.rp.tables_for_prompt = fake_tables_for_prompt
server.rp.get_method_expectations = fake_get_method_expectations
server.rp.split_text = fake_split_text
server.rp.review_chunk = fake_cancelled_review_chunk

# Let this test exercise scheduler cancellation from inside review_chunk rather
# than the explicit stage-boundary cancellation checkpoint.
original_check_cancelled = server._check_review_cancelled
server._check_review_cancelled = lambda job_id: None

try:
    server._run_review_inner(
        job_id,
        file_path,
        "general",
        tmp_dir,
    )

    job = server.review_jobs[job_id]
    check(
        "scheduler cancellation inside _run_review_inner becomes cancelled",
        job.get("status") == "cancelled",
        f"status={job.get('status')!r}",
    )
    check(
        "scheduler cancellation is not recorded as an error",
        job.get("error") is None,
        repr(job.get("error")),
    )
    check(
        "scheduler cancellation is visible in progress",
        any(
            message == "Review cancelled."
            for message in job.get("progress", [])
        ),
        repr(job.get("progress")),
    )

finally:
    server._check_review_cancelled = original_check_cancelled
    server.rp.load_document = original_load_document
    server.rp.detect_derived_input = original_detect_derived_input
    server.rp.structure_evidence = original_structure_evidence
    server.rp.tables_for_prompt = original_tables_for_prompt
    server.rp.get_method_expectations = original_get_method_expectations
    server.rp.split_text = original_split_text
    server.rp.review_chunk = original_review_chunk
    server.review_jobs = original_jobs
    shutil.rmtree(tmp_dir, ignore_errors=True)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("PASS: scheduler cancellation is classified correctly inside the real pipeline")


print("\n[cancelling a review already queued for inference]")

original_scheduler = server.llm_backend._INFERENCE_SCHEDULER
original_ensure_model = server.ensure_model
original_run_inner = server._run_review_inner

server.llm_backend._INFERENCE_SCHEDULER = server.llm_backend.InferenceScheduler(
    max_waiters=1,
    wait_timeout=5.0,
)

holder_entered = threading.Event()
release_holder = threading.Event()
review_entered_inner = threading.Event()
review_backend_called = threading.Event()
review_finished = threading.Event()


class QueuedCancellationModel(server.llm_backend.LlamaServerModel):
    def __init__(self):
        pass

    def complete(
        self,
        messages,
        max_tokens,
        sampler,
        enable_thinking,
    ):
        content = messages[-1]["content"]

        if content == "holder":
            holder_entered.set()
            release_holder.wait(2.0)
            return "holder complete"

        review_backend_called.set()
        return "review should not run"


model = QueuedCancellationModel()


def inference_holder():
    server.llm_backend.generate(
        model,
        None,
        prompt=[{"role": "user", "content": "holder"}],
        max_tokens=10,
    )


def fake_run_inner(job_id, file_path, domain, tmp_dir):
    review_entered_inner.set()
    server.llm_backend.generate(
        model,
        None,
        prompt=[{"role": "user", "content": "review"}],
        max_tokens=10,
    )


job_id = "queued-cancellation-review"
tmp_dir = Path(tempfile.mkdtemp(prefix="review-cancel-queued-"))
file_path = tmp_dir / "manuscript.txt"
file_path.write_text("test", encoding="utf-8")

server.review_jobs[job_id] = {
    "status": "running",
    "progress": [],
    "error": None,
    "thinking": None,
    "vision": None,
    "cancel_requested": False,
}

server.ensure_model = lambda: None
server._run_review_inner = fake_run_inner

holder_thread = threading.Thread(target=inference_holder)


def review_worker():
    try:
        server._run_review(
            job_id,
            file_path,
            "general",
            tmp_dir,
        )
    finally:
        review_finished.set()


review_thread = threading.Thread(target=review_worker)

try:
    holder_thread.start()
    check(
        "unrelated inference holds the scheduler",
        holder_entered.wait(1.0),
    )

    review_thread.start()
    check(
        "review reaches its inference call",
        review_entered_inner.wait(1.0),
    )

    # Wait until the review is actually queued behind the holder.
    deadline = time.monotonic() + 1.0
    while (
        server.llm_backend._INFERENCE_SCHEDULER._waiters < 1
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)

    check(
        "review is waiting for inference",
        server.llm_backend._INFERENCE_SCHEDULER._waiters == 1,
        f"waiters={server.llm_backend._INFERENCE_SCHEDULER._waiters}",
    )

    started = time.monotonic()
    server.review_jobs[job_id]["cancel_requested"] = True

    check(
        "queued review cancellation finishes promptly",
        review_finished.wait(0.50),
        "review remained queued after cancellation was requested",
    )
    elapsed = time.monotonic() - started

    check(
        "queued review never reaches model backend",
        not review_backend_called.is_set(),
    )
    check(
        "queued review cancellation is prompt",
        elapsed < 0.50,
        f"cancellation took {elapsed:.3f}s",
    )
    check(
        "queued review becomes cancelled rather than error",
        server.review_jobs[job_id]["status"] == "cancelled",
        repr(server.review_jobs[job_id]),
    )
    check(
        "unrelated active inference remains active until released",
        holder_thread.is_alive(),
    )
finally:
    release_holder.set()
    if holder_thread.is_alive():
        holder_thread.join(2.0)
    if review_thread.is_alive():
        review_thread.join(2.0)

    server.llm_backend._INFERENCE_SCHEDULER = original_scheduler
    server.ensure_model = original_ensure_model
    server._run_review_inner = original_run_inner
    server.review_jobs.pop(job_id, None)

    shutil.rmtree(tmp_dir, ignore_errors=True)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: queued review inference participates in cooperative cancellation")
