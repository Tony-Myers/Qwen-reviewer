#!/usr/bin/env python3
"""The rerun asked for credible intervals that were sitting in the evidence
appendix, then declared them unavailable. Cause: neither synthesis stage ever
received the table contents, only the manifest's list of labels."""
import sys, types
from pathlib import Path
def _stub(n,**a):
    m=types.ModuleType(n)
    for k,v in a.items(): setattr(m,k,v)
    sys.modules[n]=m
_stub("docx",Document=object);_stub("openpyxl",load_workbook=lambda *a,**k:None);
# Import the pipeline that is actually shipped. A stale copy of
# review_pipeline.py sits at the project root; with "." on the path first,
# these tests silently exercised that April file instead of app/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

# These tests were written against a scratch directory holding "paper.pdf" and
# a copy of the pipeline, so on the real repo layout they failed before running
# a single assertion. Resolve both from the project instead.
ROOT = Path(__file__).resolve().parent.parent
PIPELINE_SRC = ROOT / "app" / "review_pipeline.py"


def _paper() -> Path:
    for candidate in (
        Path(__file__).resolve().parent / "paper.pdf",
        ROOT / "inputs" / "Myers et al 2020 Discerning excellence from mediocrity in swimming.pdf",
    ):
        if candidate.exists():
            return candidate
    for candidate in sorted((ROOT / "inputs").glob("*.pdf")):
        return candidate
    print("SKIP: no PDF available (put one in tests/paper.pdf or inputs/)")
    raise SystemExit(0)

import review_pipeline as rp

fails=[]
def check(l,c,d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + (f"  {d}" if not c and d else ""))
    if not c: fails.append(l)

text, table_blocks = rp.load_document(_paper())
print(f"\n[1] extraction feeds the prompt builder")
check("tables extracted", len(table_blocks) > 0, f"{len(table_blocks)}")
tp = rp.tables_for_prompt(table_blocks)
check("prompt text is non-empty", len(tp) > 0)
check("bounded in size", len(tp) <= rp.MAX_PROMPT_TABLE_CHARS + 2000, f"{len(tp)} chars")

print("\n[2] the values the rerun said were unavailable are now in the prompt")
# breaststroke tau=0.9 credible intervals, which the rerun asked for and then
# recorded as an extraction limit
for v, why in [("0.35 – 0.82","breaststroke bi-acromial tau=0.9 CI"),
               ("0.09 – 0.44","breaststroke bi-iliac tau=0.9 CI"),
               ("0.645","breaststroke R2 tau=0.1"),
               ("-4.29","Table 1 intercept"),
               ("0.856","Table 1 R2")]:
    check(f"{v} in prompt ({why})", v in tp)

print("\n[3] the front-crawl age omission is visible in the prompt")
# Scope to the Table 2 body only: it starts at the front-crawl intercept and
# runs to the breaststroke heading. Table 1 legitimately has cubic age terms.
start = tp.find("-4.42")
end = tp.find("Breaststroke Predictors", start)
fc = tp[start:end] if start != -1 and end != -1 else ""
check("front crawl block located", len(fc) > 0)
check("front crawl block present", "Ln (Height [cm])" in fc)
check("and has no age term", "Cubic" not in fc and "Quadratic" not in fc,
      f"got: {fc[:150]!r}")

print("\n[4] both synthesis stages accept and embed it")
import inspect
for fn in (rp.synthesize_file_review, rp.synthesize_report):
    sig = inspect.signature(fn)
    check(f"{fn.__name__} takes tables_text", "tables_text" in sig.parameters)
src = PIPELINE_SRC.read_text()
check("file synthesis embeds the tables", "treat them as primary evidence" in src)
check("report synthesis embeds the tables", "check the narrative against them" in src)

print("\n[5] the new rules are present")
for probe, why in [
    ("Never describe a value as unreported", "no false absence at file level"),
    ("Before writing any \"Extraction limits\" bullet", "no false extraction limits"),
    ("reproduce the source exactly, character for character", "no invented quotations"),
    ("absent from that model's predictor list", "narrative vs table cross-check"),
]:
    check(why, probe in src)

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("All synthesis-input checks passed.")
