#!/usr/bin/env python3
"""Regression checks for honest review-progress presentation."""

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

running_match = re.search(
    r"function setReviewRunning\(running(?:,\s*completed\s*=\s*false)?\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
running_body = running_match.group("body") if running_match else ""


print("\n[running progress is explicitly indeterminate]")

check(
    "progress indicator has an indeterminate visual state",
    "indeterminate" in source.lower(),
    "the progress UI has no explicit indeterminate state",
)

check(
    "review lifecycle controls the indeterminate state",
    "indeterminate" in running_body.lower(),
    "setReviewRunning() does not own the running progress state",
)


print("\n[progress messages do not manufacture completion percentages]")

check(
    "review start does not initialise a fake percentage",
    "style.width = '0%'" not in start_body
    and 'style.width = "0%"' not in start_body,
    "review start still treats progress as a determinate percentage",
)

check(
    "progress events do not count arbitrary steps",
    "steps++" not in start_body
    and "let steps" not in start_body,
    "progress messages are still being counted as equal work units",
)

check(
    "progress events do not derive width from message count",
    "steps *" not in start_body
    and "Math.min(steps" not in start_body,
    "message count still manufactures a percentage-complete value",
)


print("\n[completion is distinct from running activity]")

check(
    "successful completion has an explicit completed state",
    re.search(
        r"d\.type\s*===\s*['\"]complete['\"].*?"
        r"setReviewRunning\(false,\s*true\)",
        start_body,
        re.S,
    ) is not None,
    "successful completion does not explicitly select the completed indicator state",
)

check(
    "completion does not masquerade as a calculated percentage",
    "style.width = '100%'" not in start_body
    and 'style.width = "100%"' not in start_body,
    "successful completion is still represented as percentage arithmetic",
)


print("\n[terminal non-completion paths stop running activity]")

check(
    "cancelled review leaves running state",
    re.search(
        r"d\.type\s*===\s*['\"]cancelled['\"].*?setReviewRunning\(false\)",
        start_body,
        re.S,
    ) is not None,
    "cancelled review does not stop the running indicator",
)

check(
    "review error leaves running state",
    re.search(
        r"d\.type\s*===\s*['\"]error['\"].*?setReviewRunning\(false\)",
        start_body,
        re.S,
    ) is not None,
    "review error does not stop the running indicator",
)

check(
    "connection loss leaves running state",
    re.search(
        r"es\.onerror\s*=.*?setReviewRunning\(false\)",
        start_body,
        re.S,
    ) is not None,
    "connection loss does not stop the running indicator",
)


if failures:
    print(f"\nFAILED: {failures}")
    sys.exit(1)

print("\nPASS: review progress reports activity without inventing percentage completion")
