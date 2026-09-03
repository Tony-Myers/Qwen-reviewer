#!/usr/bin/env python3
"""
Tests the citation check against the real run-3 report, which regressed:
its Evidence lines cited "the summary" rather than the manuscript, after a
previous run had obeyed the same instruction. Prompt rules alone proved
stochastic, so this is checked mechanically.
"""
import sys, types
from pathlib import Path
def _stub(n,**a):
    m=types.ModuleType(n)
    for k,v in a.items(): setattr(m,k,v)
    sys.modules[n]=m
_stub("docx",Document=object);_stub("openpyxl",load_workbook=lambda *a,**k:None)
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
SOURCE = text + "\n" + "\n".join(b for _, b in table_blocks)

# Verbatim from the run-3 report.
RUN3 = '''
* **Concern:** There is a logical inconsistency in the narrative description of backstroke results.
* **Evidence:** The summary states the text claims "the majority of predictors had a probability of direction <99%, yet cites arm-span (90.85%) as an exception."
* **Concern:** The distinct age structures across stroke groups may limit generalisability.
* **Evidence:** The summary notes the "front-crawl group is significantly older (mean 17.14 years) than other strokes (mean ~11.7-13.5 years) due to national competition regulations."
* **Reason:** The evidence manifest confirms "Confidence intervals reported: True," but the width matters.
'''

print("\n[1] self-citation of the pipeline's own output is caught")
probs = rp.verify_report_citations(RUN3, SOURCE)
selfcites = [p for p in probs if "own summary" in p]
check("flags 'The summary states'", any("summary states" in p.lower() for p in selfcites), str(selfcites))
check("flags 'The summary notes'", any("summary notes" in p.lower() for p in selfcites))
check("flags 'The evidence manifest confirms'", any("manifest confirms" in p.lower() for p in selfcites))

print("\n[2] a paraphrase in quotation marks is caught")
quoteprobs = [p for p in probs if "not found" in p]
check("at least one invented quotation flagged", len(quoteprobs) >= 1, str(quoteprobs)[:200])

print("\n[3] a genuine quotation verifies")
GOOD = '''* **Evidence:** The text states "The probability of direction of the majority of somatic predictors of backstroke SS were <99%, with the exception of arm-span (90.85%)".'''
gp = rp.verify_report_citations(GOOD, SOURCE)
check("real quotation not flagged", not any("not found" in p for p in gp), str(gp))
check("and no self-citation flagged", not any("own summary" in p for p in gp), str(gp))

print("\n[4] typography and punctuation drift are tolerated")
# Whitespace differs; the paper reads "coefficients (ICCs) for test-retest".
TYPO = '''* Evidence: "ICCs for test-retest  reliability ranged from 0.97 to 0.99"'''
tp = rp.verify_report_citations(TYPO, SOURCE)
check("dropped bracket and extra space tolerated", not any("not found" in p for p in tp), str(tp))
# En dash rendered as a hyphen.
DASH = '''* Evidence: Table 1 gives the interval "-4.98 - -3.56" for the intercept.'''
dp = rp.verify_report_citations(DASH, SOURCE)
check("en dash vs hyphen tolerated", not any("not found" in p for p in dp), str(dp))

print("\n[4b] but fabricated content is still caught")
FAKE = '''* Evidence: The conclusion says "shoulder breadth is important for speed in all four strokes".'''
fp = rp.verify_report_citations(FAKE, SOURCE)
check("invented quotation flagged", any("not found" in p for p in fp), str(fp))

print("\n[5] a table value verifies as a quotation")
TBL = '''* Evidence: Table 1 reports "Ln (Bi-acromial breadth [cm])" with an estimate of 0.42.'''
bp = rp.verify_report_citations(TBL, SOURCE)
check("table cell text verifies", not any("not found" in p for p in bp), str(bp))

print("\n[6] the report section renders both outcomes")
clean = rp.format_citation_check([])
check("clean report says so", "no citation refers" in clean)
dirty = rp.format_citation_check(probs)
check("problem report lists them", dirty.count("*") > len(probs))
check("section is headed", "# Citation check" in clean and "# Citation check" in dirty)

print("\n[7] a clean check must not flatter an empty one")
# A thinking-mode review quoted the manuscript nowhere -- every evidence line
# was a paraphrase -- and the citation check congratulated it on having no
# unverifiable quotations. Nothing to check is not the same as all checks passed.
none_quoted = rp.format_citation_check(
    [], "Evidence: the manuscript reports a simulation study.")
check("a report with no quotations is called out",
      "quotes the manuscript nowhere" in none_quoted, none_quoted)
some_quoted = rp.format_citation_check(
    [], 'Evidence: The text states, "a real quotation" (Page 5).')
check("a report with verified quotations still reads as clean",
      "Every quotation in this report was located" in some_quoted, some_quoted)
check("the single-argument call still works",
      "Every quotation in this report was located" in rp.format_citation_check([]))

print("\n[a short numeric quotation is still a quotation]")
# On RPAN-2026-0184 the report quoted the women's 200 m sample as
# "n = 116 173". The 116 is a marginal line number, correctly stripped from the
# extracted text, so the quotation was fabricated -- and at eleven characters
# and three words it passed under both floors in the citation check.
_SRC = "women's 200m ( n= 173). Swimmers were deidentified, however results are preserved."
_short = rp.verify_report_citations(
    'reported in the text as "n = 116 173," which is ambiguous.', _SRC)
check("a fabricated short numeric quotation is caught", len(_short) == 1, _short)
check("and the fallback names which value is real",
      _short and "173 appear in the manuscript, 116 do not" in _short[0], _short)
check("a faithful short numeric quotation passes",
      rp.verify_report_citations('given as "n= 173" for that event.', _SRC) == [])
check("a short quotation with no digits is still ignored",
      rp.verify_report_citations('it is "ambiguous" here.', _SRC) == [])

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("All citation-check tests passed.")
