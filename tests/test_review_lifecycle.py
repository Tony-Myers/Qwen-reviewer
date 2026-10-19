#!/usr/bin/env python3
"""Regression checks for review worker lifecycle state."""

import sys
import tempfile
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


print("\n[worker-level model readiness failure becomes terminal error]")

original_ensure_model = server.ensure_model
original_jobs = server.review_jobs

job_id = "lifecycle-model-failure"
tmp_dir = Path(tempfile.mkdtemp(prefix="review_lifecycle_test_"))
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
    }
}


def failing_ensure_model():
    raise RuntimeError("synthetic model readiness failure")


server.ensure_model = failing_ensure_model

escaped = None
try:
    try:
        server._run_review(
            job_id,
            file_path,
            "general",
            tmp_dir,
        )
    except Exception as exc:
        escaped = exc

    job = server.review_jobs[job_id]

    check(
        "worker-level exception does not escape review lifecycle",
        escaped is None,
        repr(escaped),
    )
    check(
        "failed worker reaches terminal error state",
        job.get("status") == "error",
        f"status={job.get('status')!r}",
    )
    check(
        "failure reason is retained",
        "synthetic model readiness failure" in (job.get("error") or ""),
        repr(job.get("error")),
    )
    check(
        "failure is visible in progress",
        any(
            "synthetic model readiness failure" in message
            for message in job.get("progress", [])
        ),
        repr(job.get("progress")),
    )
    check(
        "temporary review directory is cleaned",
        not tmp_dir.exists(),
        str(tmp_dir),
    )

finally:
    server.ensure_model = original_ensure_model
    server.review_jobs = original_jobs

    # RED behaviour currently leaves cleanup to this test because the worker's
    # outer exception bypasses _run_review_inner()'s finally block.
    if tmp_dir.exists():
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


print("\n[unexpected inner-pipeline escape is contained by worker boundary]")

original_ensure_model = server.ensure_model
original_inner = server._run_review_inner
original_jobs = server.review_jobs

job_id = "lifecycle-inner-failure"
tmp_dir = Path(tempfile.mkdtemp(prefix="review_lifecycle_inner_test_"))
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
    }
}


def ready_model():
    return None


def failing_inner(*args, **kwargs):
    raise RuntimeError("synthetic escaped pipeline failure")


server.ensure_model = ready_model
server._run_review_inner = failing_inner

escaped = None
try:
    try:
        server._run_review(
            job_id,
            file_path,
            "general",
            tmp_dir,
        )
    except Exception as exc:
        escaped = exc

    job = server.review_jobs[job_id]

    check(
        "escaped inner exception does not escape worker lifecycle",
        escaped is None,
        repr(escaped),
    )
    check(
        "escaped inner failure reaches terminal error state",
        job.get("status") == "error",
        f"status={job.get('status')!r}",
    )
    check(
        "escaped inner failure reason is retained",
        "synthetic escaped pipeline failure" in (job.get("error") or ""),
        repr(job.get("error")),
    )
    check(
        "escaped inner failure is visible in progress",
        any(
            "synthetic escaped pipeline failure" in message
            for message in job.get("progress", [])
        ),
        repr(job.get("progress")),
    )
    check(
        "escaped inner failure still cleans temporary directory",
        not tmp_dir.exists(),
        str(tmp_dir),
    )

finally:
    server.ensure_model = original_ensure_model
    server._run_review_inner = original_inner
    server.review_jobs = original_jobs

    if tmp_dir.exists():
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    raise SystemExit(1)

print("PASS: review worker boundary guarantees terminal failure state")
