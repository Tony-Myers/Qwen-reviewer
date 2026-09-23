#!/usr/bin/env python3
"""
Behavioural regression tests for the process-local inference scheduler.

The scheduler belongs at llm_backend.generate(), the common boundary used by
review, chat, Academic Chat, and CLI inference.  These tests use no live model.
"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import llm_backend  # noqa: E402


failures = 0


def ok(label, condition, detail=""):
    global failures
    if condition:
        print(f"  PASS  {label}")
    else:
        failures += 1
        suffix = f"\n        {detail}" if detail else ""
        print(f"  FAIL  {label}{suffix}")


print("\n[inference scheduler API]")

required = (
    "InferenceScheduler",
    "InferenceBusyError",
)

for name in required:
    ok(
        f"llm_backend exposes {name}",
        hasattr(llm_backend, name),
        "the bounded scheduler has not been implemented yet",
    )

if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)


Scheduler = llm_backend.InferenceScheduler
Busy = llm_backend.InferenceBusyError


print("\n[only one inference owns the backend at once]")

scheduler = Scheduler(max_waiters=2, wait_timeout=1.0)
active = 0
peak = 0
state_lock = threading.Lock()
first_entered = threading.Event()
release_first = threading.Event()
finished = []


def serial_worker(name, hold=False):
    global active, peak
    with scheduler.admit():
        with state_lock:
            active += 1
            peak = max(peak, active)
        if hold:
            first_entered.set()
            release_first.wait(2.0)
        else:
            time.sleep(0.03)
        with state_lock:
            active -= 1
        finished.append(name)


t1 = threading.Thread(target=serial_worker, args=("first", True))
t2 = threading.Thread(target=serial_worker, args=("second",))

t1.start()
ok("first inference acquired the scheduler", first_entered.wait(1.0))

t2.start()
time.sleep(0.05)

ok(
    "second inference waits rather than running concurrently",
    peak == 1 and t2.is_alive(),
    f"peak={peak}, second_alive={t2.is_alive()}",
)

release_first.set()
t1.join(2.0)
t2.join(2.0)

ok("both admitted inferences complete", sorted(finished) == ["first", "second"])
ok("backend concurrency never exceeds one", peak == 1, f"peak={peak}")


print("\n[waiting capacity is bounded]")

scheduler = Scheduler(max_waiters=1, wait_timeout=0.15)
holder_entered = threading.Event()
release_holder = threading.Event()
waiter_started = threading.Event()
waiter_finished = threading.Event()


def holder():
    with scheduler.admit():
        holder_entered.set()
        release_holder.wait(2.0)


def waiter():
    waiter_started.set()
    try:
        with scheduler.admit():
            pass
    finally:
        waiter_finished.set()


holder_thread = threading.Thread(target=holder)
waiter_thread = threading.Thread(target=waiter)

holder_thread.start()
ok("holder acquired the only inference slot", holder_entered.wait(1.0))

waiter_thread.start()
ok("one waiter entered the queue", waiter_started.wait(1.0))
time.sleep(0.03)

started = time.monotonic()
rejected = False
try:
    with scheduler.admit():
        pass
except Busy:
    rejected = True
elapsed = time.monotonic() - started

ok("a request beyond queue capacity is rejected", rejected)
ok(
    "queue-full rejection is prompt",
    elapsed < 0.10,
    f"rejection took {elapsed:.3f}s",
)

release_holder.set()
holder_thread.join(2.0)
waiter_thread.join(2.0)
ok("queued waiter is eventually released", waiter_finished.is_set())


print("\n[admission is released after an exception]")

scheduler = Scheduler(max_waiters=1, wait_timeout=0.2)

try:
    with scheduler.admit():
        raise RuntimeError("simulated generation failure")
except RuntimeError:
    pass

reacquired = False
try:
    with scheduler.admit():
        reacquired = True
except Busy:
    pass

ok("a failed generation does not leak the inference slot", reacquired)


print("\n[waiting itself is bounded]")

scheduler = Scheduler(max_waiters=1, wait_timeout=0.08)
holder_entered = threading.Event()
release_holder = threading.Event()


def timeout_holder():
    with scheduler.admit():
        holder_entered.set()
        release_holder.wait(2.0)


holder_thread = threading.Thread(target=timeout_holder)
holder_thread.start()
ok("timeout holder acquired the slot", holder_entered.wait(1.0))

started = time.monotonic()
timed_out = False
try:
    with scheduler.admit():
        pass
except Busy:
    timed_out = True
elapsed = time.monotonic() - started

ok("a queued request eventually fails rather than waiting forever", timed_out)
ok(
    "wait timeout is respected",
    0.05 <= elapsed < 0.30,
    f"wait lasted {elapsed:.3f}s",
)

release_holder.set()
holder_thread.join(2.0)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: inference admission is serialised, bounded, and exception-safe")


print("\n[public generate uses the scheduler]")

# Replace the module scheduler with a deliberately small test instance.  The
# production generate() boundary should be the owner of admission; callers
# must not need to remember to acquire a separate server-layer lock.
original_scheduler = getattr(llm_backend, "_INFERENCE_SCHEDULER", None)
test_scheduler = Scheduler(max_waiters=1, wait_timeout=0.15)
llm_backend._INFERENCE_SCHEDULER = test_scheduler

generate_active = 0
generate_peak = 0
generate_lock = threading.Lock()
generate_first_entered = threading.Event()
generate_release_first = threading.Event()
generate_results = []
generate_errors = []


class FakeServerModel(llm_backend.LlamaServerModel):
    def __init__(self):
        # Deliberately do not initialise the real HTTP-backed parent.
        pass

    def complete(self, messages, max_tokens, sampler, enable_thinking):
        global generate_active, generate_peak

        with generate_lock:
            generate_active += 1
            generate_peak = max(generate_peak, generate_active)
            ordinal = len(generate_results) + generate_active

        if not generate_first_entered.is_set():
            generate_first_entered.set()
            generate_release_first.wait(2.0)
        else:
            time.sleep(0.03)

        with generate_lock:
            generate_active -= 1

        return "answer"


fake_model = FakeServerModel()


def generate_worker(name):
    try:
        result = llm_backend.generate(
            fake_model,
            tokenizer=None,
            prompt=[{"role": "user", "content": name}],
            max_tokens=32,
        )
        generate_results.append((name, result))
    except Exception as exc:
        generate_errors.append((name, type(exc).__name__, str(exc)))


g1 = threading.Thread(target=generate_worker, args=("first",))
g2 = threading.Thread(target=generate_worker, args=("second",))

g1.start()
ok("first public generate reached the backend", generate_first_entered.wait(1.0))

g2.start()
time.sleep(0.05)

ok(
    "second public generate is held outside the backend",
    generate_peak == 1,
    f"backend peak concurrency was {generate_peak}",
)

generate_release_first.set()
g1.join(2.0)
g2.join(2.0)

ok(
    "both public generate calls complete",
    len(generate_results) == 2 and not generate_errors,
    f"results={generate_results!r}, errors={generate_errors!r}",
)
ok(
    "public generate never overlaps backend inference",
    generate_peak == 1,
    f"backend peak concurrency was {generate_peak}",
)

if original_scheduler is None:
    delattr(llm_backend, "_INFERENCE_SCHEDULER")
else:
    llm_backend._INFERENCE_SCHEDULER = original_scheduler


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: public generation is protected by bounded inference admission")


print("\n[public generate bounds its waiting queue]")

original_scheduler = llm_backend._INFERENCE_SCHEDULER
llm_backend._INFERENCE_SCHEDULER = Scheduler(
    max_waiters=1,
    wait_timeout=1.0,
)

holder_entered = threading.Event()
release_holder = threading.Event()
waiter_started = threading.Event()
holder_done = threading.Event()
waiter_done = threading.Event()


class QueueModel(llm_backend.LlamaServerModel):
    def __init__(self):
        # Avoid constructing a real backend or making any network request.
        pass

    def complete(
        self,
        messages,
        max_tokens,
        sampler,
        enable_thinking,
    ):
        holder_entered.set()
        release_holder.wait(2.0)
        return "holder"


model = QueueModel()


def public_holder():
    try:
        llm_backend.generate(
            model,
            None,
            prompt="holder",
            max_tokens=10,
        )
    finally:
        holder_done.set()


def public_waiter():
    waiter_started.set()
    try:
        llm_backend.generate(
            model,
            None,
            prompt="waiter",
            max_tokens=10,
        )
    finally:
        waiter_done.set()


holder_thread = threading.Thread(target=public_holder)
waiter_thread = threading.Thread(target=public_waiter)

try:
    holder_thread.start()
    ok(
        "public generate holder acquired inference",
        holder_entered.wait(1.0),
    )

    waiter_thread.start()
    ok(
        "one public generate entered the waiting queue",
        waiter_started.wait(1.0),
    )

    # Give the waiter enough time to enter scheduler.admit(). It cannot reach
    # QueueModel.complete() while the holder owns inference.
    time.sleep(0.05)

    started = time.monotonic()
    rejected = False
    try:
        llm_backend.generate(
            model,
            None,
            prompt="overflow",
            max_tokens=10,
        )
    except Busy:
        rejected = True
    elapsed = time.monotonic() - started

    ok(
        "public generate rejects work beyond waiting capacity",
        rejected,
        "a third logical generation was admitted despite max_waiters=1",
    )
    ok(
        "public queue-full rejection is prompt",
        elapsed < 0.10,
        f"rejection took {elapsed:.3f}s",
    )
finally:
    release_holder.set()
    holder_thread.join(2.0)
    waiter_thread.join(2.0)
    llm_backend._INFERENCE_SCHEDULER = original_scheduler

ok(
    "public holder completes after release",
    holder_done.is_set(),
)
ok(
    "queued public generate completes after release",
    waiter_done.is_set(),
)

if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: public generation queue capacity is bounded")


print("\n[scheduler configuration is validated]")

rejected_fractional_waiters = False
try:
    Scheduler(max_waiters=1.5, wait_timeout=1.0)
except (TypeError, ValueError):
    rejected_fractional_waiters = True

ok(
    "fractional waiter capacity is rejected",
    rejected_fractional_waiters,
    "waiter capacity must be an integer rather than silently truncated",
)

rejected_negative_waiters = False
try:
    Scheduler(max_waiters=-1, wait_timeout=1.0)
except (TypeError, ValueError):
    rejected_negative_waiters = True

ok("negative waiter capacity is rejected", rejected_negative_waiters)

rejected_zero_timeout = False
try:
    Scheduler(max_waiters=1, wait_timeout=0)
except (TypeError, ValueError):
    rejected_zero_timeout = True

ok(
    "zero wait timeout is rejected",
    rejected_zero_timeout,
    "configured waiting must have a positive finite bound",
)

rejected_negative_timeout = False
try:
    Scheduler(max_waiters=1, wait_timeout=-1)
except (TypeError, ValueError):
    rejected_negative_timeout = True

ok("negative wait timeout is rejected", rejected_negative_timeout)


if failures:
    print(f"\nFAILED: {failures} check(s)")
    raise SystemExit(1)

print("\nPASS: scheduler configuration is explicit and validated")
