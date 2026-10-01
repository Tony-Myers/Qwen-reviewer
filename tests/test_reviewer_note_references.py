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

    if ref.access:
        if ref.access not in rn.ACCESS_LABELS:
            problems.append(f"{where}: {ref.cite[:60]!r} has unknown access {ref.access!r}")
        if not ref.access_checked:
            problems.append(f"{where}: {ref.cite[:60]!r} records access that was not checked")
    if not ref.short:
        problems.append(f"{where}: {ref.cite[:60]!r} has no short description for the compact view")

# The compact form is derived from the citation; check the shapes it must handle.
for cite, expected in (
        ("Hyndman, R. J. (1996). Title.", "Hyndman (1996)"),
        ("Kruschke, J. K., & Liddell, T. M. (2018). Title.", "Kruschke & Liddell (2018)"),
        ("Greenland, S., Senn, S. J., & Altman, D. G. (2016). Title.", "Greenland et al. (2016)"),
        ("Lakens, D., Adolfi, F. G., Albers, C. J., et al. (2018). Title.", "Lakens et al. (2018)"),
        ("bayestestR documentation. Credible Intervals (CI). easystats.", "bayestestR documentation")):
    got = rn.Reference(cite=cite, supports="x").author_year()
    if got != expected:
        problems.append(f"author_year({cite!r}) gave {got!r}, expected {expected!r}")

# Access must come from checked metadata: an unchecked or malformed record is
# rejected by the parser rather than shown to a reader.
for bad, needle in (
        ("- cite: X (2020).\n  doi: 10.1/x\n  supports: y\n  access: open\n", "access_checked"),
        ("- cite: X (2020).\n  doi: 10.1/x\n  supports: y\n  access: free\n  access_checked: z\n", "allowed values"),
        ("- cite: X (2020).\n  doi: 10.1/x\n  supports: y\n  access: repository\n  access_checked: z\n", "access_url")):
    try:
        rn.parse_references_block(bad, "t")
        problems.append(f"a malformed access record was accepted ({needle})")
    except rn.ReferenceFormatError as exc:
        if needle not in str(exc):
            problems.append(f"wrong rejection for {needle}: {exc}")

curated = sorted(index.note_references)
print(f"{len(entries)} reference entries across {len(curated)} curated "
      f"note(s): {', '.join(curated) or 'none'}")
if problems:
    print("FAIL:")
    for line in problems:
        print(f"  - {line}")
    sys.exit(1)
print("PASS: every curated reference parses, is checked, can be followed, "
      "has a compact form, and records access only where it was checked")
