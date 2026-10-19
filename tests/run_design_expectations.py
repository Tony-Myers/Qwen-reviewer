#!/usr/bin/env python3
"""
Run the design classifier and expected-element registry over real papers.

This is step 2 of section 8 of reports/DESIGN-EXPECTATIONS.md: inspect the
false-positive rate at zero generation cost. No LLM is loaded and no report is
produced or altered.

    python3 tests/run_design_expectations.py                 # all of inputs/
    python3 tests/run_design_expectations.py path/to.pdf ... # named files
    python3 tests/run_design_expectations.py --quiet         # one line per paper

The development corpus contains no evidence syntheses, so on inputs/ every
EVIDENCE_SYNTHESIS classification is a false positive and worth reading the
signals for.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import design_expectations as de  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:                                   # noqa: BLE001
        print(f"  (pypdf failed: {exc}; trying pdfplumber)")
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join((p.extract_text() or "") for p in pdf.pages)


def read_any(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv

    if args:
        paths = [Path(a) for a in args]
    else:
        paths = sorted((ROOT / "inputs").glob("*.pdf"))

    if not paths:
        print("No input files.")
        return 0

    counts = {}
    for path in paths:
        if not path.exists():
            print(f"MISSING: {path}")
            continue
        text = read_any(path)
        verdict = de.check_document(text)
        design = verdict.design.design_class
        counts[design] = counts.get(design, 0) + 1

        print(f"\n{path.name}  ({len(text):,} chars)")
        print("  " + verdict.design.describe().replace("\n", "\n  "))

        if quiet:
            continue

        if verdict.findings:
            absent = [f for f in verdict.findings if f.kind == "absent"]
            restricted = [f for f in verdict.findings if f.kind == "restriction"]
            present = [f for f in verdict.findings if f.kind == "present"]
            print(f"  elements: {len(present)} present, {len(absent)} absent, "
                  f"{len(restricted)} restriction(s)")
            for f in absent + restricted:
                print(f"    [{f.kind}] {f.label} {f.detail}".rstrip())
        if verdict.scoped_method_text is not None:
            snippet = " ".join(verdict.scoped_method_text.split())[:160]
            print(f"  scoped analysis window: {snippet}...")

    print("\n--- summary ---")
    for design, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {design.value}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
