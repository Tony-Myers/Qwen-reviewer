#!/usr/bin/env python3
"""
Concurrency checks for server.ensure_model().

Model readiness may be requested from multiple worker threads. Exactly one
thread should perform the load transition when no model is currently loaded.

    python tests/test_model_readiness.py
"""

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

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


print("\n[concurrent model readiness loads once]")

original_model = server.model
original_tokenizer = server.tokenizer
original_load = server.load
original_current_backend = server.current_backend

load_entered = threading.Event()
release_load = threading.Event()
load_calls = []
load_calls_lock = threading.Lock()
errors = []


def blocking_load(model_name):
    with load_calls_lock:
        load_calls.append(model_name)
    load_entered.set()
    if not release_load.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release model load")
    return object(), object()


server.model = None
server.tokenizer = None
server.load = blocking_load
server.current_backend = lambda: "test"

try:
    def run_ensure():
        try:
            server.ensure_model()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=run_ensure)
    second = threading.Thread(target=run_ensure)

    first.start()

    if not load_entered.wait(timeout=1.0):
        raise RuntimeError("first ensure_model() never reached load()")

    second.start()

    # Give the second caller enough time to reach load() if readiness is not
    # serialised. The first caller is deliberately still inside blocking_load.
    time.sleep(0.1)

    calls_while_first_blocked = len(load_calls)

    release_load.set()
    first.join(timeout=1.0)
    second.join(timeout=1.0)

    check(
        "only one load begins while concurrent callers request readiness",
        calls_while_first_blocked == 1,
        f"observed {calls_while_first_blocked} load() calls",
    )
    check(
        "both readiness callers finish",
        not first.is_alive() and not second.is_alive(),
    )
    check(
        "readiness callers raise no errors",
        not errors,
        repr(errors),
    )
    check(
        "model is available after readiness",
        server.model is not None and server.tokenizer is not None,
    )
    check(
        "the model was loaded exactly once",
        len(load_calls) == 1,
        f"observed {len(load_calls)} load() calls",
    )

finally:
    release_load.set()
    server.model = original_model
    server.tokenizer = original_tokenizer
    server.load = original_load
    server.current_backend = original_current_backend


print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    raise SystemExit(1)

print("All model-readiness checks passed.")
