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

print("\n[9] marginal line numbers are removed before anything reads the text")
# A manuscript under review carries line numbers down the margin, and the PDF
# text layer puts them inside the sentences. On one submitted manuscript this
# made three correct quotations fail the citation check, fired the reliability
# banner, and fed line 129 to the model as a count of races.
NUMBERED = ("competition (Pyne et al., 2004). Hence, the data set included 129 \n"
            "finals, B-finals, C-finals, and semi-finals. Despite the findings 130 \n"
            "of Pyne et al. (2004), semi-finals were included as the reported 131 \n"
            "differences in times still indicated pacing of a calibre relevant 132 \n"
            "for analysis and their inclusion improved the sample size. 134 \n"
            "The number of clusters (K) 174 \n"
            "was chosen based on the elbow heuristic (Chu et al., 2023) focusing 175 \n"
            "on the S_Dbw index for all three clustering algorithms, finding the 176 \n"
            "qualitative intersection of the three elbows to set the value of K. 177 \n") * 3
cleaned, removed = rp.strip_marginal_line_numbers(NUMBERED)
check("a numbered manuscript is recognised", removed >= 25, str(removed))
check("the sentence is restored",
      "Hence, the data set included\nfinals, B-finals" in cleaned, cleaned[:200])
hay = rp._normalise_for_match(cleaned)
punct = rp._strip_punctuation(hay)
nospace = re.sub(r"\s+", "", punct)
check("a quotation spanning a line break now verifies",
      rp._missing_fragment("The number of clusters (K) was chosen based on the "
                           "elbow heuristic", hay, punct, nospace) is None)

# Stripping every trailing integer would eat real data: a table row ending in a
# count is indistinguishable from a line number except by the sequence.
TABLE = ("Table 1. Athlete demographics.\nVariable Male Female\nN 22 10\n"
         "Age (y) 22 4 18 3\nTier 5-World Class 1 1\n"
         "Tier 4-Elite/International 9 2\n") * 8
untouched, removed_table = rp.strip_marginal_line_numbers(TABLE)
check("table rows ending in a number are left alone",
      removed_table == 0 and untouched == TABLE, str(removed_table))
check("a short document is left alone",
      rp.strip_marginal_line_numbers(
          "".join("a line %d\n" % i for i in range(1, 10)))[1] == 0)
check("numbering that restarts each page is still caught",
      rp.strip_marginal_line_numbers(
          "".join("".join("body text %d\n" % i for i in range(1, 31))
                  for _ in range(3)))[1] == 90)
check("the removal is reported, not silent",
      "LAST_EXTRACTION_NOTES" in PIPELINE_SRC.read_text(encoding="utf-8")
      and "Extraction: " in (ROOT / "app" / "server.py").read_text(encoding="utf-8"))

print("\n[10] mathematical italic letters do not hide a statistic")
# "p < 0.05" written in Word is U+1D45D, not "p": the manifest reported
# "P-values reported: False" for a paper whose results table is all p-values,
# and the prompt uses that manifest to decide what the model may call absent.
MATHS = "were significant (\U0001D45D < 0.05 in Kruskal-Wallis tests)"
check("the italic p is folded for detection",
      rp.structure_evidence("x.pdf", MATHS, []).has_p_values)
check("an ASCII p still works",
      rp.structure_evidence("x.pdf", "significant (p < 0.05)", []).has_p_values)
check("folding does not alter the text itself",
      rp.fold_mathematical_letters("plain text") == "plain text")

print("\n[11] damaged tables are recognised for re-reading from the page image")
# Each signal comes from damage actually measured. A Kruskal-Wallis table kept
# every number but scattered its headers onto orphan lines; a Bayesian results
# table printed a cell as "s0"; a centroid table broke "Parabolic" into
# "Paraboli" and "c". A clean table must be left alone: rendering a page and
# asking a model to read it costs a minute each.
DETACHED = ("[TABLE_START]\nSource: pdfplumber_text\nPage: 21\nLabel: Table 5\n"
            "p-Value\nFreedom\nModel\n"
            "K-Means\t3\t3.95\t0.27\n"
            "Men's Hierarchical\t3\t4.86\t0.18\n"
            "Freestyle Mixture\t3\t3.89\t0.27\n[TABLE_END]")
MALFORMED = ("[TABLE_START]\nSource: pdfplumber_text\nPage: 8\n"
             "WeeklyPoolVolume\t-0.02\t0.98\nTimeloss\t82%\ts0\n"
             "4-weekRollingPool\t-0.00\t1.00\n[TABLE_END]")
BROKEN_WORD = ("[TABLE_START]\nSource: pdfplumber_text\nPage: 18\n"
               "1\tPositive\t0.103\t0.096\n3\tParaboli\t-0.123\t-0.039\nc\n"
               "4\tAll-Out\t0.096\t-0.049\n[TABLE_END]")
CLEAN_TABLE = ("[TABLE_START]\nSource: pdfplumber\nPage: 19\n"
               "Men's 100m Freestyle\t138.489\nWomen's 100m Freestyle\t114.976\n"
               "Men's 200m Freestyle\t242.013\n[TABLE_END]")
check("detached headers are caught", "carry no numbers" in rp.table_looks_damaged(DETACHED))
check("a malformed cell is caught", "s0" in rp.table_looks_damaged(MALFORMED))
check("a word broken across lines is caught",
      "broken across lines" in rp.table_looks_damaged(BROKEN_WORD))
check("a clean table is left alone", rp.table_looks_damaged(CLEAN_TABLE) == "",
      rp.table_looks_damaged(CLEAN_TABLE))
check("vision is off unless asked for", rp.VISION_TABLES is False)

blocks = [(21, DETACHED), (19, CLEAN_TABLE)]
same, notes = rp.rescue_damaged_tables(ROOT / "nothing.pdf", blocks)
check("nothing happens while the flag is off", same == blocks and notes == [])

# Vision is an enhancement: when it cannot deliver, the review proceeds on the
# text layer and the report says so rather than looking as though it never asked.
rp.VISION_TABLES = True
try:
    out, notes = rp.rescue_damaged_tables(ROOT / "nothing.pdf", blocks)
    check("a failed re-read leaves the tables untouched", out == blocks)
    check("and is reported rather than silent",
          bool(notes) and any(("could not be re-read" in n)
                              or ("were not read" in n) for n in notes),
          str(notes))
finally:
    rp.VISION_TABLES = False

print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("All extraction checks passed.")
