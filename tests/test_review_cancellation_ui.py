#!/usr/bin/env python3
"""Regression checks for the browser review-cancellation lifecycle."""

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


print("\n[review UI exposes an explicit cancellation control]")

check(
    "review controls contain a cancel button",
    'id="cancelReviewBtn"' in source,
    "no dedicated review cancellation button is present",
)

check(
    "cancel control calls a dedicated cancellation function",
    'onclick="cancelReview()"' in source,
    "cancel control is not wired to cancelReview()",
)

check(
    "browser distinguishes an active review from a completed report",
    "activeReviewJobId" in source,
    "no active-review job identifier is present",
)


print("\n[running review remains protected from a second start]")

refresh_match = re.search(
    r"function refreshReviewButton\(forceDisabled\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
refresh_body = refresh_match.group("body") if refresh_match else ""

check(
    "review button state accounts for an active review",
    "activeReviewJobId" in refresh_body,
    "refreshReviewButton() can visually re-enable Start while a review is active",
)


print("\n[active job identity is established before status streaming]")

start_match = re.search(
    r"async function startReview\(\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
start_body = start_match.group("body") if start_match else ""

job_assignment = start_body.find("activeReviewJobId")
event_source = start_body.find("new EventSource")

check(
    "startReview records the active job id",
    job_assignment >= 0,
    "startReview() does not retain the running job id",
)

check(
    "active job id is recorded before EventSource starts",
    job_assignment >= 0
    and event_source >= 0
    and job_assignment < event_source,
    "cancellation identity is not established before status streaming",
)


print("\n[cancel request targets only the active review]")

cancel_match = re.search(
    r"async function cancelReview\(\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
cancel_body = cancel_match.group("body") if cancel_match else ""

check(
    "cancelReview exists",
    cancel_match is not None,
    "async function cancelReview() is missing",
)

check(
    "cancelReview requires an active job",
    "activeReviewJobId" in cancel_body,
    "cancelReview() is not tied to the active review",
)

check(
    "cancelReview calls the server cancellation endpoint",
    "/cancel" in cancel_body
    and "fetch(" in cancel_body,
    "cancelReview() does not POST to the cancellation endpoint",
)

check(
    "cancel request uses POST",
    "method: 'POST'" in cancel_body or 'method: "POST"' in cancel_body,
    "cancellation request is not explicitly POST",
)

check(
    "accepted cancellation becomes a cancelling UI state",
    "Cancelling" in cancel_body,
    "cancelReview() does not visibly enter a cancelling state",
)


print("\n[failed cancellation does not masquerade as a failed review]")

check(
    "cancel request failure does not replace the report with a review error",
    "showErr(" not in cancel_body,
    "cancelReview() uses the review-level error renderer for a cancellation-request failure",
)

progress_helper_match = re.search(
    r"function appendReviewProgress\(message\)\s*\{(?P<body>.*?)\n\}",
    source,
    re.S,
)
progress_helper_body = (
    progress_helper_match.group("body") if progress_helper_match else ""
)

check(
    "cancel request failure delegates to review progress",
    "appendReviewProgress(" in cancel_body,
    "cancelReview() does not report cancellation-request failure through review progress",
)

check(
    "review progress helper writes to the progress log",
    "progressLog" in progress_helper_body
    and "appendChild(" in progress_helper_body,
    "appendReviewProgress() does not write a message to the review progress log",
)

check(
    "cancel request failure says the review is still running",
    "still running" in cancel_body.lower(),
    "the UI does not make clear that a failed cancellation leaves the review running",
)


print("\n[cancelled SSE is a normal terminal outcome]")

check(
    "status handler recognises cancelled",
    "d.type === 'cancelled'" in start_body
    or 'd.type === "cancelled"' in start_body,
    "startReview() has no cancelled SSE branch",
)

cancelled_branch = re.search(
    r"""if\s*\(\s*d\.type\s*===\s*['"]cancelled['"]\s*\)\s*\{(?P<body>.*?)\}""",
    start_body,
    re.S,
)
cancelled_body = cancelled_branch.group("body") if cancelled_branch else ""

check(
    "cancelled status closes the event stream",
    "es.close()" in cancelled_body,
    "cancelled SSE does not close EventSource",
)

check(
    "cancelled status clears active job identity",
    "activeReviewJobId" in cancelled_body
    and "null" in cancelled_body,
    "cancelled SSE leaves the active review id behind",
)

check(
    "cancelled status is not rendered as an error",
    "showErr(" not in cancelled_body,
    "cancelled SSE is incorrectly presented as an error",
)


print("\n[other terminal paths also release active-review state]")

complete_branch = re.search(
    r"""if\s*\(\s*d\.type\s*===\s*['"]complete['"]\s*\)\s*\{(?P<body>.*?)\}""",
    start_body,
    re.S,
)
error_branch = re.search(
    r"""if\s*\(\s*d\.type\s*===\s*['"]error['"]\s*\)\s*\{(?P<body>.*?)\}""",
    start_body,
    re.S,
)

complete_body = complete_branch.group("body") if complete_branch else ""
error_body = error_branch.group("body") if error_branch else ""

check(
    "completion clears active review identity",
    "activeReviewJobId" in complete_body and "null" in complete_body,
    "completed review remains marked active",
)

check(
    "server error clears active review identity",
    "activeReviewJobId" in error_body and "null" in error_body,
    "failed review remains marked active",
)

check(
    "completed report identity remains separate",
    "let currentJobId = null;" in source
    and "currentJobId = jobId || null;" in source,
    "completed-review identity was removed or conflated with active identity",
)


if failures:
    print(f"\nFAILED: {failures}")
    sys.exit(1)

print("\nPASS: browser review cancellation has a distinct, terminal lifecycle")
