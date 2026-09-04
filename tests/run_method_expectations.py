#!/usr/bin/env python3
"""
Dry run of the analysis-framework registry over real papers.

Step 2 of the discipline in constraint 18.3.4: measure across the corpus
before proposing any integration. No model is loaded, no report is produced
and nothing in app/ is altered.

    python3 tests/run_method_expectations.py                  # all of inputs/
    python3 tests/run_method_expectations.py path/to.pdf ...
    python3 tests/run_method_expectations.py --quiet           # one line each
    python3 tests/run_method_expectations.py --no-supplement   # body only

Success conditions, from 18.5:
  - zero findings on the sixteen published papers, or a finding confirmed true
    against the PDF;
  - the missing priors and convergence diagnostics in RJSP-2026-0327 detected
    as computed absences;
  - the section reads as a list of elements not located, with the searched
    terms shown, and not as an accusation.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "app"))

import design_expectations as de        # noqa: E402
import method_expectations as me        # noqa: E402


def read_pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def read_any(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return read_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv
    supplement = "--no-supplement" not in sys.argv

    paths = [Path(a) for a in args] if args else sorted((ROOT / "inputs").glob("*.pdf"))
    fired = 0

    for path in paths:
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            print(f"MISSING: {path}")
            continue

        text = read_any(path)
        design = de.classify_design(text).design_class
        is_syn = design is de.DesignClass.EVIDENCE_SYNTHESIS
        verdict = me.check_method_elements(text, is_evidence_synthesis=is_syn,
                                           include_supplement=supplement)

        absent = verdict.absent
        if absent:
            fired += 1

        print(f"\n{path.name}  ({len(text):,} chars, design={design.value})")
        print(f"  {verdict.gate.describe()}")
        if verdict.scope_note:
            print(f"  {verdict.scope_note}")
        if quiet:
            if absent:
                print(f"  ABSENT: {', '.join(f.key for f in absent)}")
            continue
        for f in verdict.findings:
            mark = "ABSENT " if f.kind == "absent" else "present"
            print(f"    [{mark}] {f.label}")

    print(f"\n--- summary: {fired} of {len(paths)} documents produced at least "
          f"one absence ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
