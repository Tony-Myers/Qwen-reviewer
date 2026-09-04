#!/usr/bin/env python3
"""
Diagnostic for section 18.4 of reports/EVALUATION.md.

The manifest for RJSP-2026-0327 records

    Analysis performed by the review itself: unclassified (scoped to the
    methods section)

while the whole-document classifier returned `bayesian_mixed_effects`. The
paper's Methods do describe Bayesian modelling, so the scoped answer looks
wrong. A registry keyed on MethodClass would inherit that error.

This script establishes what `scoped_synthesis_text()` actually returned and
why `classify_method()` then produced `unclassified` on it. It loads no model,
generates nothing and writes nothing. It is read-only over `app/`.

    python3 tests/diagnose_scoped_method.py inputs/RJSP-2026-0327_reviewer.pdf
    python3 tests/diagnose_scoped_method.py               # all of inputs/*.pdf
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import design_expectations as de           # noqa: E402
import review_pipeline as rp               # noqa: E402


def pct(offset: int, total: int) -> str:
    return f"{100.0 * offset / total:.1f}%" if total else "n/a"


def flatten(s: str, n: int = 200) -> str:
    return " ".join(s.split())[:n]


def which_cue(text_lower: str):
    """Report the first analysis cue and where it sits."""
    m = de._SYNTHESIS_ANALYSIS_CUES.search(text_lower)
    return m


def pattern_report(label: str, body: str) -> None:
    """
    Replay the _METHOD_PATTERNS loop and say, for every class, whether its
    required patterns matched and whether an exclusion then killed it.

    The exclusion column is the point of this: a class can be silently
    suppressed by a term that is ordinary vocabulary in the paper's own field.
    """
    print(f"\n  --- _METHOD_PATTERNS over {label} ({len(body):,} chars) ---")
    any_row = False
    for method_class, required_any, exclude_any in rp._METHOD_PATTERNS:
        hits = [p for p in required_any if re.search(p, body)]
        if not hits:
            continue
        any_row = True
        kills = [p for p in (exclude_any or []) if re.search(p, body)]
        state = "EXCLUDED by " + ", ".join(kills) if kills else "matched"
        print(f"    {method_class.value:<34} {state}")
        print(f"      required hit: {', '.join(hits[:4])}")
    if not any_row:
        print("    (no class matched any required pattern)")


def diagnose(path: Path) -> None:
    print("=" * 78)
    print(path.name)
    print("=" * 78)

    text, _tables = rp.load_document(path)
    for note in rp.LAST_EXTRACTION_NOTES:
        print(f"  extraction: {note}")
    print(f"  document: {len(text):,} chars")

    # --- design axis -------------------------------------------------------
    verdict = de.classify_design(text)
    print(f"  {verdict.describe()}")

    # --- whole-document method --------------------------------------------
    full_class = rp.classify_method(text)
    print(f"  classify_method(full text)     = {full_class.value}")

    stripped = de.strip_back_matter(text)
    print(f"  strip_back_matter kept {len(stripped):,} chars "
          f"({pct(len(stripped), len(text))} of the document)")

    # --- the scoped window -------------------------------------------------
    lowered = text.lower()
    cue = which_cue(lowered)
    if cue is None:
        print("\n  scoped_synthesis_text: NO CUE FOUND -> returns None")
        print("  (the manifest line would not be printed at all)")
        return

    print(f"\n  first analysis cue: {cue.group(0)!r}")
    print(f"    at char {cue.start():,} ({pct(cue.start(), len(text))} into the document)")
    print(f"    context: ...{flatten(text[max(0, cue.start()-180):cue.start()+220], 400)}...")

    scoped = de.scoped_synthesis_text(text)
    if scoped is None:
        print("  scoped_synthesis_text returned None")
        return

    start = max(0, cue.start() - 400)
    raw_window = text[start:start + 6000]
    end = de._METHODS_END.search(raw_window)
    print(f"\n  window before truncation: {len(raw_window):,} chars")
    if end:
        print(f"  _METHODS_END fired at offset {end.start():,} within the window, "
              f"on {end.group(0)!r}")
        print(f"    the line it cut on: "
              f"{flatten(raw_window[end.start():end.start()+120], 120)!r}")
    else:
        print("  _METHODS_END did not fire; window kept to the full 6000 chars")
    print(f"  scoped window delivered: {len(scoped):,} chars")
    print(f"    head: {flatten(scoped, 260)}")
    print(f"    tail: ...{flatten(scoped[-260:], 260)}")

    scoped_class = rp.classify_method(scoped)
    print(f"\n  classify_method(scoped window) = {scoped_class.value}")

    # --- why -------------------------------------------------------------
    pattern_report("the scoped window", de.strip_back_matter(scoped))
    pattern_report("the full document", stripped)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    paths = [Path(a) for a in args] if args else sorted((ROOT / "inputs").glob("*.pdf"))
    for p in paths:
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            print(f"MISSING: {p}")
            continue
        diagnose(p)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
