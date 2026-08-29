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

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("All programmatic-guard tests passed.")
