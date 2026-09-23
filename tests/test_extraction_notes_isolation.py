"""Regression test: extraction notes belong to the document that produced them."""

import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import review_pipeline as rp


fails = []


def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail:
            print(f"        {detail}")
        fails.append(label)


print("\n[extraction notes are returned with their own document]")

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    paper_a = tmp / "paper-a.txt"
    paper_b = tmp / "paper-b.txt"
    paper_a.write_text("A", encoding="utf-8")
    paper_b.write_text("B", encoding="utf-8")

    # Each document gets a different deterministic extraction repair.
    def fake_read(path):
        if path == paper_a:
            return (
                "".join(
                    "".join(f"A body text {i}\n" for i in range(1, 31))
                    for _ in range(3)
                ),
                [],
            )
        return (
            "".join(
                "".join(f"B body text {i}\n" for i in range(1, 41))
                for _ in range(3)
            ),
            [],
        )

    with patch.object(rp, "_read_document", side_effect=fake_read):
        result_a = rp.load_document(paper_a)
        result_b = rp.load_document(paper_b)

    check(
        "load_document returns text, tables, and notes",
        len(result_a) == 3 and len(result_b) == 3,
        f"A returned {len(result_a)} value(s); B returned {len(result_b)}",
    )

    if len(result_a) == 3 and len(result_b) == 3:
        text_a, tables_a, notes_a = result_a
        text_b, tables_b, notes_b = result_b

        check(
            "A keeps A's extraction notes",
            any("90 marginal line number(s)" in note for note in notes_a),
            repr(notes_a),
        )
        check(
            "B keeps B's extraction notes",
            any("120 marginal line number(s)" in note for note in notes_b),
            repr(notes_b),
        )
        check(
            "returned note lists are independent objects",
            notes_a is not notes_b,
        )


print("\n[one review cannot overwrite another review's returned notes]")

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    paper_a = tmp / "paper-a.txt"
    paper_b = tmp / "paper-b.txt"
    paper_a.write_text("A", encoding="utf-8")
    paper_b.write_text("B", encoding="utf-8")

    a_loaded = threading.Event()
    allow_a_to_finish = threading.Event()
    results = {}

    def fake_read(path):
        if path == paper_a:
            return (
                "".join(
                    "".join(f"A body text {i}\n" for i in range(1, 31))
                    for _ in range(3)
                ),
                [],
            )
        return (
            "".join(
                "".join(f"B body text {i}\n" for i in range(1, 41))
                for _ in range(3)
            ),
            [],
        )

    def review_a():
        results["a"] = rp.load_document(paper_a)
        a_loaded.set()
        allow_a_to_finish.wait(timeout=5)

    def review_b():
        a_loaded.wait(timeout=5)
        results["b"] = rp.load_document(paper_b)
        allow_a_to_finish.set()

    with patch.object(rp, "_read_document", side_effect=fake_read):
        ta = threading.Thread(target=review_a)
        tb = threading.Thread(target=review_b)
        ta.start()
        tb.start()
        ta.join(timeout=5)
        tb.join(timeout=5)

    check("both simulated reviews finished",
          not ta.is_alive() and not tb.is_alive())

    if (
        "a" in results
        and "b" in results
        and len(results["a"]) == 3
        and len(results["b"]) == 3
    ):
        notes_a = results["a"][2]
        notes_b = results["b"][2]

        check(
            "A still owns its notes after B loads",
            any("90 marginal line number(s)" in note for note in notes_a),
            repr(notes_a),
        )
        check(
            "B owns its own notes",
            any("120 marginal line number(s)" in note for note in notes_b),
            repr(notes_b),
        )
        check(
            "A and B own separate note lists",
            notes_a is not notes_b,
        )


if fails:
    print(f"\nFAILED: {len(fails)} check(s)")
    raise SystemExit(1)

print("\nPASS: extraction notes are per-document data, not shared review state")
