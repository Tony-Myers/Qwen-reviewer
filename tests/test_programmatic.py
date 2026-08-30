#!/usr/bin/env python3
"""
Two programmatic guards, added after a run silently reviewed the previous
run's own evidence appendix and produced a report that read entirely normally.
"""
import sys, types
from pathlib import Path
def _stub(n,**a):
    m=types.ModuleType(n)
    for k,v in a.items(): setattr(m,k,v)
    sys.modules[n]=m
_stub("docx",Document=object);_stub("openpyxl",load_workbook=lambda *a,**k:None)
sys.path.insert(0,".")
import review_pipeline as rp

fails=[]
def check(l,c,d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + (f"  {d}" if not c and d else ""))
    if not c: fails.append(l)

paper_text, tb = rp.load_document(Path("paper.pdf"))
derived_text = Path("derived_input.md").read_text(encoding="utf-8")

print("\n[1] the pipeline's own output is recognised")
d = rp.detect_derived_input(derived_text)
check("evidence appendix detected", len(d) >= 3, str(d))
check("real manuscript not flagged", rp.detect_derived_input(paper_text) == [],
      str(rp.detect_derived_input(paper_text)))
check("empty input safe", rp.detect_derived_input("") == [])
check("ordinary prose not flagged",
      rp.detect_derived_input("We fitted a Bayesian model. Results are in Table 1.") == [])

print("\n[2] predictor lists are read off the tables")
models = rp.extract_model_predictors(tb)
check("four stroke models found", len(models) == 4, str(list(models)))
for name in ("Front Crawl Predictors","Breaststroke Predictors",
             "Backstroke Predictors","Butterfly Predictors"):
    check(f"{name} present", name in models, str(list(models)))

print("\n[3] each list matches Table 2 in the manuscript")
expected = {
    "Front Crawl Predictors":  {"body fat","bi-acromial breadth","height"},
    "Breaststroke Predictors": {"age","body fat","bi-acromial breadth","bi-iliac breadth"},
    "Backstroke Predictors":   {"age","body fat","seated height","wrist girth",
                                "calf girth","bi-iliac breadth","arm span"},
    "Butterfly Predictors":    {"age","body fat","calf girth","ankle girth",
                                "bi-acromial breadth","bi-iliac breadth"},
}
for name, want in expected.items():
    got = set(models.get(name, []))
    check(f"{name} exact", got == want, f"got {sorted(got)}")

print("\n[4] the asymmetry the reviews kept missing is stated outright")
summary = rp.summarise_model_predictors(tb)
check("age absence is asserted",
      "age: present in" in summary and "ABSENT from Front Crawl Predictors" in summary,
      summary[:200])
check("descriptive table did not leak in",
      "Fron Fron" not in summary and "Sitting" not in summary and " l:" not in summary)
check("summary is compact", len(summary.split("\n")) <= 20, f"{len(summary.splitlines())} lines")

print("\n[5] it reaches the prompt")
tp = rp.tables_for_prompt(tb)
check("predictor summary leads the tables block", tp.startswith("Predictor lists read directly"))
check("ABSENT statement in the prompt", "ABSENT from Front Crawl Predictors" in tp)

print("\n[6] a single-model paper produces no spurious comparison")
one = [(1, "Model 1\nIntercept\t1.0\t0.5 - 1.5\nAge\t0.2\t0.1 - 0.3\nR2\t0.5\n")]
check("no summary for one model", rp.summarise_model_predictors(one) == "")

print("\n[7] a badly extracted table is flagged, not fed in silently")
supp = [b for _, b in tb if "time (s)" in b]
check("supplementary table located", len(supp) == 1, str(len(supp)))
warn = rp.table_fragmentation_warning(supp[0]) if supp else ""
check("fragmentation detected", warn.startswith("WARNING"), warn[:80])
check("warning forbids computing with it", "do not raise a data-integrity concern" in warn.lower())
clean_tbl = [b for _, b in tb if "Bi-acromial Breadth" in b and "time (s)" not in b]
check("clean coefficient table not flagged",
      all(rp.table_fragmentation_warning(b) == "" for b in clean_tbl),
      f"{len(clean_tbl)} clean tables")
tp2 = rp.tables_for_prompt(tb)
check("warning reaches the prompt", "did not extract cleanly" in tp2)

print("\n[8] fabricated numbers are caught")
SRC = paper_text + "\n" + "\n".join(b for _, b in tb)
# The exact false concern raised in run 5.
FAB = ('* Evidence: The table reports a speed of "1.04 m/s" alongside a time of '
       '"13.79s" for a 100m event, implying 7.25 m/s.')
fp = rp.verify_report_citations(FAB, SRC)
check("13.79 flagged as absent", any("13.79" in p for p in fp), str(fp)[:200])
check("1.04 not flagged (it is real)", not any("Number 1.04" in p for p in fp), str(fp)[:200])
REAL = '* Evidence: Table 1 reports a coefficient of 0.42 with R2 Bayes of 0.856.'
rp2 = rp.verify_report_citations(REAL, SRC)
check("genuine numbers not flagged", not any("does not appear" in p for p in rp2), str(rp2))

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("All programmatic-guard tests passed.")
