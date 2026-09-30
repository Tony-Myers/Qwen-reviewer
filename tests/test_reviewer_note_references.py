#!/usr/bin/env python3
"""
Curation rules for the references in resources/reviewer_notes/.

    python3 tests/test_reviewer_note_references.py

A malformed references block is skipped at run time so that one bad entry
cannot take Academic Chat down. This test is what stops it going unnoticed:
it fails on any entry the parser rejected, and on any entry that would give
the reader nothing to follow.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import reviewer_notes as rn  # noqa: E402

index = rn.NotesIndex()
problems = list(index.reference_errors)

entries = [(note, "", ref) for note, refs in index.note_references.items()
           for ref in refs]
entries += [(note, heading, ref)
            for (note, heading), refs in index.section_references.items()
            for ref in refs]

section_keys = {(p.note, p.heading) for p in index.passages}
for (note, heading) in index.section_references:
    if (note, heading) not in section_keys:
        problems.append(
            f"{note} - {heading}: this section's references can never be "
            "shown, because no indexed passage carries that heading")

for note, heading, ref in entries:
    where = f"{note} - {heading}" if heading else note
    if not ref.link() and not ref.isbn:
        problems.append(f"{where}: {ref.cite[:60]!r} has nothing to follow")
    if not ref.checked:
        problems.append(
            f"{where}: {ref.cite[:60]!r} has no checked field; record when "
            "and how it was confirmed")
    if ref.doi and not ref.doi.startswith("10."):
        problems.append(f"{where}: {ref.doi!r} does not look like a DOI")

curated = sorted(index.note_references)
print(f"{len(entries)} reference entries across {len(curated)} curated "
      f"note(s): {', '.join(curated) or 'none'}")
if problems:
    print("FAIL:")
    for line in problems:
        print(f"  - {line}")
    sys.exit(1)
print("PASS: every curated reference parses, is checked and can be followed")
