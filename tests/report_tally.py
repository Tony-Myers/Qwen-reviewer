#!/usr/bin/env python3
"""
Tally reviews you have already run, grouped by reasoning mode.

The browser offers a per-review choice between instruct and thinking mode, and
each report records which it used. This reads a folder of those reports and
scores them on the figures the pipeline computes for itself, so alternating the
two over real work becomes an evaluation rather than an impression.

    .venv/bin/python tests/report_tally.py reports/
    .venv/bin/python tests/report_tally.py reports/ reviews/ --by passes

Why this rather than a controlled sweep: a sweep runs the same paper twice and
costs an hour per comparison. This costs nothing, uses papers you had to review
anyway, and accumulates. The trade is that the papers differ between groups, so
it needs more of them before it means anything.

HOW MANY IS ENOUGH. An A/A test on this pipeline -- two identical
configurations, four papers -- differed by 3 in 'high', 9 in 'self' and 6 in
'quot'. That is the noise you are trying to see past. Ten reviews per mode is a
sensible minimum, and a difference smaller than the figures above is not a
difference. The tool prints the per-review spread so you can judge for yourself.
"""

import argparse
import importlib.util
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("sweep", ROOT / "tests" / "sampler_sweep.py")
_sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sweep)

MODE_RE = re.compile(r"^Reasoning:\s*(\w+)", re.M)
PASSES_RE = re.compile(r"^Synthesis:\s*(\d+)\s*pass", re.M)
PIPELINE_RE = re.compile(r"^Pipeline:\s*(\w+)", re.M)


def group_of(report: str, by: str) -> str:
    if by == "passes":
        found = PASSES_RE.search(report)
        return f"{found.group(1)} passes" if found else "1 pass"
    if by == "pipeline":
        found = PIPELINE_RE.search(report)
        return found.group(1) if found else "unknown"
    found = MODE_RE.search(report)
    # Reports written before the mode was recorded cannot be assigned to one.
    return found.group(1) if found else "unrecorded"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folders", nargs="+", type=Path)
    ap.add_argument("--by", choices=("mode", "passes", "pipeline"), default="mode")
    args = ap.parse_args()

    reports = []
    for folder in args.folders:
        if not folder.exists():
            print(f"No such folder: {folder}")
            return 2
        for path in sorted(folder.rglob("*.md")):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "# Local peer-review report" not in text:
                continue           # evidence appendices and anything else
            reports.append((path, text))

    if not reports:
        print("No review reports found. Reports are written to the folder given "
              "to --output-dir, or delivered through the browser and saved by you.")
        return 1

    groups: dict = {}
    for path, text in reports:
        groups.setdefault(group_of(text, args.by), []).append(_sweep.score(text))

    print(f"{len(reports)} report(s), grouped by {args.by}\n")
    header = (f"{'group':14s} {'n':>3} {'high':>12} {'self':>12} {'quot':>12} "
              f"{'echo':>10} {'banner':>7}")
    print(header)
    print("-" * len(header))

    def cell(values):
        if not values:
            return "-"
        mean = statistics.mean(values)
        return f"{mean:5.1f} ({min(values)}-{max(values)})"

    for name in sorted(groups):
        rows = groups[name]
        banners = sum(r["banner"] for r in rows)
        print(f"{name:14s} {len(rows):>3} "
              f"{cell([r['high'] for r in rows]):>12} "
              f"{cell([r['self-cite'] for r in rows]):>12} "
              f"{cell([r['bad-quote'] for r in rows]):>12} "
              f"{cell([r['echo'] for r in rows]):>10} "
              f"{banners:>3}/{len(rows):<3}")

    print("-" * len(header))
    print("\nMean (min-max) per review. 'high' higher is better; the rest lower.")
    small = [n for n, rows in groups.items() if len(rows) < 10]
    if small:
        print(f"\nFewer than 10 reviews in: {', '.join(small)}. An A/A test on "
              "this pipeline varied by 3 in 'high', 9 in 'self' and 6 in 'quot' "
              "over four papers, so treat these as provisional.")
    if "unrecorded" in groups:
        print(f"\n{len(groups['unrecorded'])} report(s) predate the Reasoning "
              "header and cannot be assigned to a mode.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
