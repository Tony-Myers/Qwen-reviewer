#!/usr/bin/env python3
"""
Regression checks for browser-initiated service restart.

The browser must delegate restart to scripts/qwen_service.sh, which owns both
managed processes and their PID files. Tests must never start or stop the real
service.

    python tests/test_server_restart.py
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import server  # noqa: E402


failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"PASS: {label}")
    else:
        print(f"FAIL: {label}")
        if detail:
            print(f"      {detail}")
        failures.append(label)


print("[1] restart helper delegates to the service manager")

original_popen = server.subprocess.Popen
original_sleep = server.time.sleep

popen_calls = []


class DummyProcess:
    pass


def fake_popen(cmd, **kwargs):
    popen_calls.append((cmd, kwargs))
    return DummyProcess()


server.subprocess.Popen = fake_popen
server.time.sleep = lambda _seconds: None

try:
    server._restart_after_response("qwen38")
finally:
    server.subprocess.Popen = original_popen
    server.time.sleep = original_sleep

check(
    "restart launches exactly one detached process",
    len(popen_calls) == 1,
    repr(popen_calls),
)

if popen_calls:
    cmd, kwargs = popen_calls[0]

    check(
        "restart delegates to qwen_service.sh",
        cmd[0] == str(ROOT / "scripts" / "qwen_service.sh"),
        repr(cmd),
    )
    check(
        "service manager receives the restart command and selected model",
        cmd[1:] == ["restart", "--model", "qwen38", "--no-open"],
        repr(cmd),
    )
    check(
        "restart process is detached from the FastAPI process",
        kwargs.get("start_new_session") is True,
        repr(kwargs),
    )
    check(
        "restart runs from the project root",
        kwargs.get("cwd") == str(ROOT),
        repr(kwargs),
    )
    check(
        "browser restart does not launch start_server.sh directly",
        "start_server.sh" not in " ".join(map(str, cmd)),
        repr(cmd),
    )


print("\n[2] endpoint schedules even a same-model restart")

original_model_name = server.MODEL_NAME
original_cached = server._cached_snapshot_for_model
original_thread = server.threading.Thread
original_restart_scheduled = server.restart_scheduled

thread_calls = []


class DummyThread:
    def __init__(self, *, target, args, daemon):
        thread_calls.append({
            "target": target,
            "args": args,
            "daemon": daemon,
            "started": False,
        })
        self.record = thread_calls[-1]

    def start(self):
        self.record["started"] = True


try:
    server.MODEL_NAME = server.resolve_model_choice("qwen38")
    server._cached_snapshot_for_model = lambda _model: Path("/tmp/fake-model")
    server.threading.Thread = DummyThread
    server.restart_scheduled = False

    response = asyncio.run(server.restart_server({"model": "qwen38"}))

finally:
    server.MODEL_NAME = original_model_name
    server._cached_snapshot_for_model = original_cached
    server.threading.Thread = original_thread
    server.restart_scheduled = original_restart_scheduled

check(
    "same configured model now schedules a real restart",
    isinstance(response, dict) and response.get("status") == "restarting",
    repr(response),
)
check(
    "restart endpoint schedules exactly one worker",
    len(thread_calls) == 1,
    repr(thread_calls),
)

if thread_calls:
    call = thread_calls[0]
    check(
        "restart worker targets the service-manager helper",
        call["target"] is server._restart_after_response,
    )
    check(
        "restart worker retains the selected model alias",
        call["args"] == ("qwen38",),
        repr(call["args"]),
    )
    check(
        "restart worker is daemonised and started",
        call["daemon"] is True and call["started"] is True,
        repr(call),
    )


print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    raise SystemExit(1)

print("All server-restart checks passed.")
