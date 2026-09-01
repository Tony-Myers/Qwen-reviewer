#!/usr/bin/env python3
"""
Compare sampler configurations on the same paper, and score the reports.

This exists because every sampler judgement in this project so far has been
mine rather than measured, and several of my expectations about the live
pipeline have turned out to be wrong. Unsloth publish 0.7 / 0.80 / 20 with
repetition_penalty 1.0 and presence_penalty 1.5 for Qwen3.8 in non-thinking
mode; the pipeline runs 0.2 / 0.80 / 20 and has never sent either penalty, so
whatever llama-server defaults to has been in force unexamined.

Two things make an objective comparison possible now, and neither existed a
day ago: per-concern confidence is COMPUTED from whether quotations verify
against the manuscript, and the citation check counts unverifiable claims. So a
configuration can be scored without anyone reading the reports.

MEASURED NOISE FLOOR. The first sweep run compared "current" against
"repen-1.0" over four papers and produced what looked like a large effect. It
was not: llama-server's /props reports repeat_penalty 1.0 already, so the two
configurations were sending an identical sampler and the whole thing was an
accidental A/A test. What it measured instead was the variance of this pipeline
at a FIXED setting, over four papers:

    metric        A     B      per-paper swing
    high          1     4
    self-cite    16     7
    bad-quote    22    18      one paper went 2 -> 8
    echo          2     0

So a difference smaller than roughly 3 in "high", 9 in "self-cite" or 6 in
"bad-quote" on a handful of papers means nothing whatever. Every sweep now
includes an A/A pair by default for exactly this reason: read the real
comparison against that pair, not against zero.

    .venv/bin/python tests/sampler_sweep.py inputs/some-paper.pdf
    .venv/bin/python tests/sampler_sweep.py inputs/a.pdf inputs/b.pdf --configs current,repen-1.0
    .venv/bin/python tests/sampler_sweep.py inputs/a.pdf --passes 1 --keep

Needs llama-server running. Each configuration is a full review, so a sweep of
four configurations over two papers is eight reviews: budget accordingly, and
close Unsloth first.

What the columns mean:
  high/mod/low   concerns by computed confidence -- HIGH IS THE ONE THAT MATTERS
  self-cite      Evidence lines citing the pipeline's own summary
  bad-quote      quotations that could not be located in the manuscript
  bad-num        numbers that could not be located
  echo           Evidence lines that merely restate their concern
  banner         the report opened admitting nothing was manuscript-supported
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Each entry is a name and the environment the pipeline reads its sampler from.
# "current" must stay exactly as the pipeline ships, or the baseline is not one.
CONFIGS = {
    "current": {},
    # An exact duplicate of "current". Its difference from "current" is this
    # pipeline's noise at a fixed setting, measured on the same papers in the
    # same session -- the only honest yardstick for any other row.
    "a-a-control": {},
    "repen-1.0": {"QWEN_REPETITION_PENALTY": "1.0"},
    "vendor": {"QWEN_TEMPERATURE": "0.7", "QWEN_REPETITION_PENALTY": "1.0"},
    "vendor+pp": {"QWEN_TEMPERATURE": "0.7", "QWEN_REPETITION_PENALTY": "1.0",
                  "QWEN_PRESENCE_PENALTY": "1.5"},
    # Thinking mode uses the vendor's thinking-mode numbers. Reasoning tokens
    # may count against the generation limit, so the synthesis limit is raised
    # with it -- otherwise the report truncates and the comparison is worthless.
    "thinking": {"QWEN_TEMPERATURE": "1.0", "QWEN_TOP_P": "0.95",
                 "LLAMA_ENABLE_THINKING": "1",
                 "LLAMA_REASONING_EFFORT": "low",
                 "QWEN_SYNTHESIS_MAX_TOKENS": "4000"},
}

_CONF = re.compile(r"^\s*[-*]?\s*\**\s*Confidence:?\**\s*:?\s*(\w+)", re.M | re.I)


def score(report: str) -> dict:
    """Count what the report's own mechanical checks concluded."""
    levels = [m.lower() for m in _CONF.findall(report)]
    return {
        "high": levels.count("high"),
        "mod": levels.count("moderate"),
        "low": levels.count("low"),
        "self-cite": report.count("Cites this pipeline's own summary"),
        "bad-quote": (report.count("Quotation not found")
                      + report.count("Quotation only partly found")),
        "bad-num": len(re.findall(r"^\* Number \S+ does not appear", report, re.M)),
        "echo": report.count("Evidence line restates the concern"),
        "banner": int("No concern in this report is supported" in report),
        "chars": len(report),
    }


def run_one(pdf: Path, name: str, env_overrides: dict, passes: int,
            out_dir: Path) -> dict:
    env = dict(os.environ)
    env.update(env_overrides)
    env["REVIEW_PASSES"] = str(passes)
    target = out_dir / name
    target.mkdir(parents=True, exist_ok=True)
    python = ROOT / ".venv" / "bin" / "python"
    if not python.exists():
        python = Path(sys.executable)

    started = time.time()
    proc = subprocess.run(
        [str(python), str(ROOT / "app" / "review_pipeline.py"), str(pdf),
         "--output-dir", str(target)],
        env=env, capture_output=True, text=True, timeout=7200,
    )
    elapsed = time.time() - started

    reports = sorted(target.glob("*review*.md"))
    if proc.returncode != 0 or not reports:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return {"name": name, "failed": True, "secs": elapsed,
                "why": tail[-1][:120] if tail else f"exit {proc.returncode}"}

    result = score(reports[-1].read_text(encoding="utf-8"))
    result.update({"name": name, "failed": False, "secs": elapsed,
                   "report": reports[-1]})
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+", type=Path)
    ap.add_argument("--configs", default="current,a-a-control,vendor",
                    help="comma-separated names from: " + ", ".join(CONFIGS))
    ap.add_argument("--passes", type=int, default=1,
                    help="REVIEW_PASSES per review (default 1: vary one thing at a time)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--keep", action="store_true", help="keep the reports")
    args = ap.parse_args()

    names = [n.strip() for n in args.configs.split(",") if n.strip()]
    unknown = [n for n in names if n not in CONFIGS]
    if unknown:
        print(f"Unknown configuration(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(CONFIGS)}")
        return 2
    missing = [p for p in args.pdfs if not p.exists()]
    if missing:
        print("No such file: " + ", ".join(str(p) for p in missing))
        return 2

    out_dir = args.out or Path(tempfile.mkdtemp(prefix="sweep-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(args.pdfs) * len(names)
    print(f"{total} review(s): {len(args.pdfs)} paper(s) x {len(names)} configuration(s), "
          f"{args.passes} pass(es) each")
    print(f"Reports under {out_dir}\n")

    header = (f"{'paper':26s} {'config':11s} {'high':>4} {'mod':>4} {'low':>4} "
              f"{'self':>4} {'quot':>4} {'num':>4} {'echo':>4} {'ban':>3} {'mins':>5}")
    print(header)
    print("-" * len(header))

    rows = []
    for pdf in args.pdfs:
        for name in names:
            row = run_one(pdf, name, CONFIGS[name], args.passes,
                          out_dir / pdf.stem[:40])
            row["paper"] = pdf.stem[:26]
            rows.append(row)
            if row["failed"]:
                print(f"{row['paper']:26s} {name:11s}  FAILED  {row['why']}")
            else:
                print(f"{row['paper']:26s} {name:11s} {row['high']:>4} {row['mod']:>4} "
                      f"{row['low']:>4} {row['self-cite']:>4} {row['bad-quote']:>4} "
                      f"{row['bad-num']:>4} {row['echo']:>4} {row['banner']:>3} "
                      f"{row['secs']/60:>5.1f}")
            sys.stdout.flush()

    print("-" * len(header))
    good = [r for r in rows if not r["failed"]]
    if good:
        print("\nTotals per configuration (higher 'high' is better; "
              "lower self/quot/num/echo is better):\n")
        print(f"  {'config':11s} {'high':>5} {'self':>5} {'quot':>5} {'num':>5} {'echo':>5}")
        for name in names:
            same = [r for r in good if r["name"] == name]
            if not same:
                continue
            print(f"  {name:11s} {sum(r['high'] for r in same):>5} "
                  f"{sum(r['self-cite'] for r in same):>5} "
                  f"{sum(r['bad-quote'] for r in same):>5} "
                  f"{sum(r['bad-num'] for r in same):>5} "
                  f"{sum(r['echo'] for r in same):>5}")
        control = [r for r in good if r["name"] == "a-a-control"]
        baseline = [r for r in good if r["name"] == "current"]
        if control and baseline:
            print("\nNoise floor from the A/A pair (current vs a-a-control, "
                  "identical settings):")
            for key, label in (("high", "high"), ("self-cite", "self"),
                               ("bad-quote", "quot"), ("echo", "echo")):
                gap = abs(sum(r[key] for r in baseline) - sum(r[key] for r in control))
                print(f"    {label:5s} differed by {gap}")
            print("  Treat any other configuration's difference from 'current' "
                  "as real only if it clearly exceeds these.")
        else:
            print("\nNo A/A pair in this run. Add 'a-a-control' to --configs, "
                  "or you have nothing to judge a difference against: at a "
                  "fixed setting this pipeline has varied by 3 in 'high', 9 in "
                  "'self' and 6 in 'quot' across four papers.")

    if not args.keep and not args.out:
        shutil.rmtree(out_dir, ignore_errors=True)
    else:
        print(f"\nReports kept in {out_dir}")
    return 0 if all(not r["failed"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
