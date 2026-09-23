#!/usr/bin/env python3
"""Regression checks for completed-review state across a server restart."""

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


restart_match = re.search(
    r"async function waitForRestart\(expectedModel\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
restart_body = restart_match.group("body") if restart_match else ""

invalidate_match = re.search(
    r"function invalidateCompletedReviewAfterRestart\(\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
invalidate_body = invalidate_match.group("body") if invalidate_match else ""


print("\n[successful restart invalidates the old server-backed review identity]")

check(
    "restart recovery has an explicit completed-review invalidation helper",
    invalidate_match is not None,
    "no dedicated completed-review restart boundary exists",
)

check(
    "successful restart invokes completed-review invalidation",
    "invalidateCompletedReviewAfterRestart()" in restart_body,
    "waitForRestart() leaves the old review identity live after reconnecting",
)

check(
    "old review job identity is cleared",
    "currentJobId = null" in invalidate_body,
    "the browser can still address the old process's review job",
)


print("\n[restart preserves the locally rendered report]")

check(
    "restart invalidation does not clear report HTML",
    "innerHTML = ''" not in invalidate_body
    and 'innerHTML = ""' not in invalidate_body,
    "completed report content is discarded during restart invalidation",
)

check(
    "restart invalidation does not clear raw report Markdown",
    "_raw = ''" not in invalidate_body
    and '_raw = ""' not in invalidate_body
    and "_raw = null" not in invalidate_body,
    "locally downloadable/copyable report Markdown is discarded",
)


print("\n[stale server-backed controls are made unavailable]")

check(
    "ask controls are disabled after restart",
    "askBtn" in invalidate_body
    and "disabled" in invalidate_body,
    "the stale review still presents Ask as an available server-backed action",
)

check(
    "restart state is explained to the user",
    "restart" in invalidate_body.lower()
    and (
        "unavailable" in invalidate_body.lower()
        or "no longer" in invalidate_body.lower()
    ),
    "the UI does not explain why server-backed review actions changed",
)


print("\n[appendix availability follows browser ownership]")

check(
    "cached appendix is distinguished from server-only appendix",
    "_rawAppendix" in invalidate_body,
    "restart invalidation does not inspect whether the appendix is already cached locally",
)

check(
    "uncached appendix controls are disabled after restart",
    "appendixToggle" in invalidate_body
    and "disabled" in invalidate_body,
    "an uncached appendix still appears retrievable from the restarted server",
)

check(
    "cached appendix is not discarded",
    "_rawAppendix = ''" not in invalidate_body
    and '_rawAppendix = ""' not in invalidate_body
    and "_rawAppendix = null" not in invalidate_body,
    "restart invalidation discards an appendix already owned by the browser",
)


if failures:
    print(f"\nFAILED: {failures}")
    sys.exit(1)

print("\nPASS: completed reports survive restart without retaining stale server state")
