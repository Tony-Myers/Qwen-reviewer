#!/usr/bin/env python3
"""Regression checks for browser handling of an interrupted review connection."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / "app" / "chat.html"
source = CHAT.read_text(encoding="utf-8")

failures = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        failures.append(label)


start_match = re.search(
    r"async function startReview\(\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
start_body = start_match.group("body") if start_match else ""

error_match = re.search(
    r"es\.onerror\s*=\s*\(\)\s*=>\s*\{(?P<body>.*?)\n\s*\};",
    start_body,
    re.S,
)
error_body = error_match.group("body") if error_match else ""


print("\n[review connection loss is an explicit interrupted state]")

check(
    "review EventSource has a connection-loss handler",
    error_match is not None,
    "startReview() has no EventSource error handler",
)

check(
    "connection loss closes the abandoned event stream",
    "es.close()" in error_body,
    "the failed EventSource is left open",
)

check(
    "connection loss releases active review identity",
    "activeReviewJobId" in error_body and "null" in error_body,
    "the browser continues to treat the lost review as active",
)

check(
    "connection loss restores review controls",
    "setReviewRunning(false)" in error_body,
    "review controls remain in their running state after connection loss",
)


print("\n[connection loss does not imply a recoverable review]")

loss_text = error_body.lower()

check(
    "connection-loss message identifies the interrupted review",
    "review" in loss_text,
    "the message only describes a generic server/network failure",
)

check(
    "connection-loss message says the review cannot be resumed",
    "cannot be resumed" in loss_text
    or "can't be resumed" in loss_text
    or "cannot resume" in loss_text,
    "the UI does not state the application's non-resumable review contract",
)

check(
    "connection-loss message tells the user to start again",
    "start" in loss_text
    and ("again" in loss_text or "new review" in loss_text),
    "the UI gives no actionable recovery instruction",
)


print("\n[connection loss is distinct from normal terminal outcomes]")

check(
    "connection loss is not described as cancellation",
    "cancelled" not in loss_text
    and "canceled" not in loss_text,
    "an interrupted review is incorrectly presented as user cancellation",
)

check(
    "connection loss is not described as completion",
    "complete" not in loss_text
    and "completed" not in loss_text,
    "an interrupted review is incorrectly presented as completed",
)


if failures:
    print(f"\nFAILED: {failures}")
    sys.exit(1)

print("\nPASS: interrupted review connection has explicit non-resumable semantics")
