#!/usr/bin/env python3
"""
Regression tests for table extraction, against the paper whose review
prompted the change (Myers et al. 2020).

Before: Tables 1-3 (every coefficient) were invisible to the pipeline, because
pdfplumber's default strategy needs ruled lines in both directions and those
tables are set booktabs-style. Only the two ruled supplementary tables were
found, and the manifest reported "Tables extracted: 2" as though that were all
of them.
"""

import re
import sys
import types
from pathlib import Path


def _stub(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod


_stub("docx", Document=object)
_stub("openpyxl", load_workbook=lambda *a, **k: None)
_stub("pypdf", PdfReader=object)

sys.path.insert(0, str(Path(__file__).parent))
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

import review_pipeline as rp  # noqa: E402

PDF = _paper()
TABLE_PAGES = {18, 19, 20, 21}      # where the tables actually are
PROSE_PAGES = set(range(1, 18))     # everything before them is narrative

failures = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        failures.append(label)


candidates = rp.extract_tables_pdfplumber(PDF)
selected = rp.deduplicate_and_select_best_tables(candidates)
alltext = "\n".join(
    " ".join(str(c) for c in row) for t in selected for row in t["rows"]
)

print("\n[1] the results tables are found at all")
check("some tables selected", len(selected) > 0)
pages = {t["page"] for t in selected}
check("page 18 (Table 1) extracted", 18 in pages, str(sorted(pages)))
check("page 19 (Table 2 body) extracted", 19 in pages, str(sorted(pages)))

print("\n[2] no narrative page is mistaken for a table")
leaked = sorted(p for p in pages if p in PROSE_PAGES)
check("no prose pages selected", not leaked, f"leaked pages {leaked}")
check("selection stays small", len(selected) <= 8, f"{len(selected)} tables")

print("\n[3] the coefficients a reviewer needs are present")
for value, why in [
    ("-4.29", "Table 1 intercept"),
    ("0.42", "bi-acromial breadth, across strokes"),
    ("0.856", "R2 Bayes, Table 1"),
    ("0.77", "front crawl bi-acromial at tau=0.9"),
    ("0.645", "breaststroke R2 at tau=0.1"),
    ("70.17", "Table 3 breaststroke prediction"),
]:
    check(f"{value} present ({why})", value in alltext)

print("\n[4] numbers are not split across cells")
# "-4.42" must survive intact rather than becoming "-4." and "42"
check("intervals kept whole", "-5.94 – -3.35" in alltext or "-5.94 - -3.35" in alltext,
      "CI split apart")
orphan = re.findall(r"(?<![\d.])-\d+\.(?=\s*\|)", alltext)
check("no orphaned numeric fragments", len(orphan) == 0, f"{len(orphan)} found")

print("\n[5] stacked sub-tables stay identifiable")
for header in ("Breaststroke Predictors", "Backstroke Predictors", "Butterfly Predictors"):
    check(f"'{header}' retained", header in alltext)

print("\n[6] tables carry their captions")
labels = [str(t.get("label") or "") for t in selected]
check("Table 1 labelled", any("Table 1" in l for l in labels), str(labels))
check("no label taken from an in-text mention",
      not any(t["page"] in PROSE_PAGES for t in selected), str(labels))

print("\n[7] the finding the old review got wrong is now visible")
# Front crawl's model has no age term, while the other strokes do. The old
# review asserted the opposite because it never saw Table 2.
t2 = [t for t in selected if t["page"] == 19 and "continued" in str(t.get("label"))]
check("Table 2 body located", len(t2) == 1, f"{len(t2)} candidates")
t2text = "\n".join(" ".join(str(c) for c in row) for row in t2[0]["rows"]) if t2 else ""
fc = t2text.split("Breaststroke Predictors")[0]
check("front crawl block has no age term",
      "Cubic" not in fc and "Quadratic" not in fc,
      f"age term in front crawl block: {fc[:200]!r}")
check("other strokes do have age terms",
      "Quadratic (Age)" in alltext and "Cubic(age)" in alltext)

print("\n[8] prompt guards are in place")
srctext = PIPELINE_SRC.read_text(encoding="utf-8")
check("evidence must quote the manuscript", "Never cite this pipeline's own intermediate output" in srctext)
check("quantile subsetting guard", "Quantile regression does NOT split the sample" in srctext)
check("internal-consistency checks", "Internal-consistency checks" in srctext)
check("no-claim-outrunning-evidence rule", "Claims must not outrun the evidence" in srctext)

print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("All extraction checks passed.")
