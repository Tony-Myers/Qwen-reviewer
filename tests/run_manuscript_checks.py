#!/usr/bin/env python3
"""
Run the deterministic manuscript checks over real papers and report firing
rates. No LLM is loaded and no report is produced or altered.

    python3 tests/run_manuscript_checks.py                    # all of inputs/
    python3 tests/run_manuscript_checks.py paper.pdf
    python3 tests/run_manuscript_checks.py paper.pdf --appendix appendix.md
    python3 tests/run_manuscript_checks.py --quiet            # counts only

The development corpus is sixteen published papers. A check that fires often
there is either finding something real in every paper, which is implausible, or
is too loose to ship.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import manuscript_checks as mc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def read_pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def read_tables(appendix: Path) -> list:
    """Pull [TABLE_START]...[TABLE_END] blocks out of an evidence appendix."""
    if not appendix or not appendix.exists():
        return []
    text = appendix.read_text(encoding="utf-8", errors="replace")
    blocks, current = [], None
    for line in text.splitlines():
        if "[TABLE_START]" in line:
            current = []
            continue
        if "[TABLE_END]" in line:
            if current:
                blocks.append("\n".join(current))
            current = None
            continue
        if current is not None:
            current.append(line)
    return blocks


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in sys.argv
    appendix = None
    if "--appendix" in sys.argv:
        appendix = Path(sys.argv[sys.argv.index("--appendix") + 1])
        args = [a for a in args if a != str(appendix)]

    paths = [Path(a) for a in args] or sorted((ROOT / "inputs").glob("*.pdf"))
    tables = read_tables(appendix)

    totals = Counter()
    papers_firing = Counter()
    for path in paths:
        if not path.exists():
            print(f"MISSING: {path}")
            continue
        text = read_pdf_text(path) if path.suffix.lower() == ".pdf" else path.read_text()
        findings = mc.run_all(text, tables)
        keys = Counter(f.key for f in findings)
        totals.update(keys)
        papers_firing.update(set(keys))
        print(f"\n{path.name}  ({len(text):,} chars, {len(tables)} table block(s))")
        if not findings:
            print("  no findings")
            continue
        print("  " + ", ".join(f"{k} x{v}" for k, v in keys.most_common()))
        if not quiet:
            for f in findings:
                print("   -", f.line()[:400])

    print("\n--- summary over", len(paths), "paper(s) ---")
    for key, n in totals.most_common():
        print(f"  {key}: {n} finding(s) across {papers_firing[key]} paper(s)")
    if not totals:
        print("  nothing fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
