#!/usr/bin/env python3
"""Regression check for blocking bibliographic verification in its async endpoint."""

import asyncio
import sys
import threading
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


print("\n[reference verification does not block the event loop]")

original_verify = server.verify_academic_reference

verification_entered = threading.Event()
release_verification = threading.Event()
received = []


class SyntheticVerification:
    def to_dict(self):
        return {"status": "synthetic_verified"}


def blocking_verify(**kwargs):
    received.append(kwargs)
    verification_entered.set()
    if not release_verification.wait(timeout=2.0):
        raise RuntimeError("test timed out waiting to release reference verification")
    return SyntheticVerification()


async def exercise():
    server.verify_academic_reference = blocking_verify

    loop_progressed = asyncio.Event()

    async def independent_work():
        await asyncio.sleep(0)
        loop_progressed.set()

    # Release from outside the event loop. If bibliographic verification runs
    # on the event-loop thread, unrelated coroutine work cannot progress before
    # this helper releases the blocking fake.
    releaser = threading.Thread(
        target=lambda: (
            verification_entered.wait(timeout=1.0),
            threading.Event().wait(0.2),
            release_verification.set(),
        ),
        daemon=True,
    )
    releaser.start()

    verify_task = asyncio.create_task(
        server.academic_verify_reference(
            {
                "title": "Synthetic article",
                "author": "Example Author",
                "year": 2026,
                "venue": "Synthetic Journal",
                "doi": "10.1234/example",
            }
        )
    )
    other_task = asyncio.create_task(independent_work())

    try:
        await asyncio.sleep(0.05)

        entered = verification_entered.is_set()
        responsive_before_release = (
            loop_progressed.is_set() and not release_verification.is_set()
        )

        result = await asyncio.wait_for(verify_task, timeout=1.0)
        await asyncio.wait_for(other_task, timeout=1.0)
        releaser.join(timeout=1.0)

        return entered, responsive_before_release, result
    finally:
        release_verification.set()
        releaser.join(timeout=1.0)
        server.verify_academic_reference = original_verify


entered, responsive, result = asyncio.run(exercise())

check(
    "bibliographic verification started",
    entered,
)
check(
    "event loop remains responsive while verification is blocked",
    responsive,
    "verify_academic_reference() currently occupies the FastAPI event-loop thread",
)
check(
    "verification still completes after release",
    result == {"status": "synthetic_verified"},
)
check(
    "endpoint passes only bibliographic metadata",
    received == [
        {
            "title": "Synthetic article",
            "author": "Example Author",
            "year": 2026,
            "venue": "Synthetic Journal",
            "doi": "10.1234/example",
        }
    ],
    repr(received),
)

print()
if failures:
    print(f"{len(failures)} failure(s): {failures}")
    raise SystemExit(1)

print("PASS: bibliographic verification is offloaded from the event loop")
