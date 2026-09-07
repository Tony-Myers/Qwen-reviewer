#!/usr/bin/env python3
"""
The reviewer-notes mode of /api/review/{job_id}/ask, without a model.

What can be checked without generating anything is the plumbing: that an
answer's provenance has the shape every source will use, that the trailing
"Used:" line is parsed rather than guessed at, and that an interaction reaches
the log in a form worth reading later. The answer itself needs the model and
is checked by using it.

    python3 tests/test_notes_chat.py

Requires the app's dependencies, so it skips where fastapi is absent rather
than failing: it is meant to run in the virtual environment the server runs in.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

try:
    import server
except Exception as exc:                                      # pragma: no cover
    # Not only ImportError: importing the module registers the routes, and a
    # missing optional dependency surfaces there rather than at the import.
    print(f"SKIPPED: the app's dependencies are not importable here ({exc}).")
    print("Run this with the virtual environment the server uses.")
    raise SystemExit(0)

failures = []


def check(label, condition):
    print(("  " if condition else "  FAIL: ") + label)
    if not condition:
        failures.append(label)


print("the provenance vocabulary")
# Two sources answer today. Two more are named so that adding them costs a
# label and nothing else -- the interface reads provenance.label and never
# branches on which source produced the answer.
for source in (server.SOURCE_MANUSCRIPT, server.SOURCE_NOTES,
               server.SOURCE_REASONING, server.SOURCE_REASONING_REF):
    p = server.provenance(source)
    check(f"{source!r} has a label", p["label"].startswith("Source: "))
    check(f"{source!r} has the full shape",
          set(p) == {"source", "label", "passages", "used", "resolved", "reference"})
check("a reserved source is not silently unlabelled",
      "unknown" not in server.provenance(server.SOURCE_REASONING)["label"])
check("nothing populates a reference yet",
      server.provenance(server.SOURCE_NOTES)["reference"] is None)

print("the used line is parsed, not guessed")
cases = [
    ("An answer.\n\nUsed: [1], [3]", ("An answer.", [1, 3], False, True)),
    ("Not covered.\nUsed: none", ("Not covered.", [], True, True)),
    ("Body.\n\nUsed: 2", ("Body.", [2], False, True)),
    ("Body.\n\nused: [1]\n\n", ("Body.", [1], False, True)),
    ("Multi\nline\nanswer.\n\nUsed: [2], [1]", ("Multi\nline\nanswer.", [2, 1], False, True)),
]
for text, expected in cases:
    check(f"{text.splitlines()[-1]!r} parses", server.parse_used(text) == expected)

# A missing line is not a model reporting that nothing applied. Conflating the
# two would file a parsing failure in the log as evidence about the notes.
_, used, said_none, found = server.parse_used("An answer with no trailing line.")
check("a missing line is recorded as missing, not as 'none'",
      used == [] and said_none is False and found is False)

print("an interaction reaches the log")
with tempfile.TemporaryDirectory() as tmp:
    original = server.NOTES_LOG_PATH
    server.NOTES_LOG_PATH = Path(tmp) / "nested" / "reviewer-notes-chat.jsonl"
    try:
        record = {"question": "is an R-hat of 1.05 acceptable?",
                  "retrieved": [{"note": "N", "heading": "H", "score": 0.42}],
                  "used": [{"note": "N", "heading": "H"}],
                  "no_suitable_note": False}
        server.log_notes_interaction(record)
        server.log_notes_interaction(dict(record, no_suitable_note=True))
        lines = server.NOTES_LOG_PATH.read_text(encoding="utf-8").strip().split("\n")
        check("the directory is created if absent", server.NOTES_LOG_PATH.exists())
        check("one line per interaction", len(lines) == 2)
        parsed = [json.loads(line) for line in lines]
        check("each line is valid JSON on its own", len(parsed) == 2)
        check("the question is recorded", parsed[0]["question"].startswith("is an R-hat"))
        check("retrieved sections carry their scores",
              parsed[0]["retrieved"][0]["score"] == 0.42)
        check("the sections used are recorded separately from those retrieved",
              parsed[0]["used"] == [{"note": "N", "heading": "H"}])
        check("a miss is recorded as a miss", parsed[1]["no_suitable_note"] is True)
    finally:
        server.NOTES_LOG_PATH = original

# Logging must never take an answer down with it.
server.NOTES_LOG_PATH = Path("/does/not/exist/and/cannot/be/made/x.jsonl")
try:
    server.log_notes_interaction({"question": "q"})
    check("a log that cannot be written does not raise", True)
except Exception:
    check("a log that cannot be written does not raise", False)

print()
print(f"{'FAILED' if failures else 'passed'}: {len(failures)} failure(s)")
raise SystemExit(1 if failures else 0)
