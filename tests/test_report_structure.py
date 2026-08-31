#!/usr/bin/env python3
"""
Covers the report-structure additions: severity tiers, computed per-concern
confidence, the prioritised action table and the verdict-phrasing detector.

Confidence is computed from the checks the pipeline already performs rather
than asked of the model, because a model's stated confidence is a token
prediction: the run that inverted this corpus's medication finding asserted it
without hedging. The action table is rendered from the severity labels already
written, never generated again -- an earlier template asked for the same
material twice and produced two headings over one list of items.

Both marker styles are exercised: runs have emitted "**Concern:**" and bare
"Concern:" interchangeably.
"""
import sys, types, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
def _stub(n,**a):
    m=types.ModuleType(n)
    [setattr(m,k,v) for k,v in a.items()]; sys.modules[n]=m
_stub("docx",Document=object); _stub("openpyxl",load_workbook=lambda *a,**k:None)
root=Path.home()/"mnt/local-llm/qwen35-review"
sys.path.insert(0,str(root/"app"))
import review_pipeline as rp

SOURCE = ("Table 4. ML model performance. glm 0.998 0.013 0.134 0.211\n"
          "Best models were highlighted based on the lowest MAE on the train set.\n"
          "In ML, the best model is typically selected based on model performance "
          "on the training sets, which in our case was the glm model.\n"
          "Twenty-seven recreational cyclists completed baseline tests.\n")

# Style A: bold markers, as the cycling run produced them
REPORT_A = """# Overall synopsis
* A study of cycling performance.

# Major strengths
* **Strength:** Nested cross-validation.
* **Evidence:** Outer repeated train/test splits with inner LOOCV.

# Directly supported concerns
* **Concern:** Model selection based on training set performance introduces bias.
* **Severity:** Critical
* **Evidence:** The caption states models were selected on the "lowest MAE on the train set".
* **Why it matters:** This is a fundamental error that renders the comparison invalid.

* **Concern:** The reported test MAE is inconsistent between text and table.
* **Severity:** Editorial
* **Evidence:** Table 4 reports 0.211 while the narrative states 0.221.
* **Why it matters:** It undermines confidence in the reported values.

* **Concern:** Subgroup analyses lack multiplicity correction.
* **Severity:** Substantive
* **Evidence:** The file summary notes that five characteristics were tested.
* **Why it matters:** Type I error risk rises.

# Verification prompts
* **Check:** Whether baseline performance was a predictor in the change model.
* **Reason:** Regression to the mean.

# Extraction limits
* **Limit:** Hyperparameters are in Supplemental Table S5.

# Overall confidence
* Moderate.
"""

# Style B: plain markers, as the BMI and sleep runs produced them
REPORT_B = REPORT_A.replace("**", "")

F = 0
def ok(label, cond, detail=""):
    global F
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"   {detail}" if not cond and detail else ""))
    if not cond: F += 1

for name, report in (("bold markers", REPORT_A), ("plain markers", REPORT_B)):
    print(f"\n[{name}]")
    annotated = rp.annotate_concern_confidence(report, SOURCE)
    ok("verified quotation -> High", "Confidence: High" in annotated)
    ok("self-citation -> Low",
       "Confidence: Low — the evidence cites this pipeline's own summary" in annotated)
    ok("table value -> High", annotated.count("Confidence: High") == 2, annotated.count("Confidence: High"))
    ok("one line per concern", annotated.count("* Confidence:") == 3,
       str(annotated.count("* Confidence:")))
    ok("running twice changes nothing",
       rp.annotate_concern_confidence(annotated, SOURCE) == annotated)
    ok("no concern text lost", "Subgroup analyses lack multiplicity" in annotated)

    table = rp.format_action_list(annotated)
    ok("action list renders", "# Prioritised actions" in table)
    ok("Critical row present", "| Critical |" in table)
    ok("Editorial maps to Low", "| Low |" in table)
    ok("Substantive maps to High", "| High |" in table)
    ok("verification prompt is Medium", "| Medium |" in table)
    lines = [l for l in table.splitlines() if l.startswith("| ") and "---" not in l]
    ok("one header + four items", len(lines) == 5, str(len(lines)))
    ok("Critical sorts first", lines[1].startswith("| Critical |"), lines[1][:40])

    over = rp.overclaim_problems(annotated)
    ok("'fundamental error' flagged", any("fundamental error" in p for p in over), str(over))
    ok("'renders ... invalid' flagged", any("renders" in p for p in over), str(over))

print("\n[degenerate input must not raise or corrupt]")
for label, bad in (("empty", ""),
                   ("no concerns section", "# Overall synopsis\n* Something.\n"),
                   ("heading but no bullets", "# Directly supported concerns\n\n# Verification prompts\n")):
    try:
        out = rp.annotate_concern_confidence(bad, SOURCE)
        t = rp.format_action_list(bad)
        ok(f"{label}: survives", isinstance(out, str) and isinstance(t, str))
    except Exception as exc:
        ok(f"{label}: survives", False, f"{type(exc).__name__}: {exc}")
ok("no table when nothing to list", rp.format_action_list("# Overall synopsis\n* x\n") == "")
ok("clean report yields no overclaims", rp.overclaim_problems("A measured statement.") == [])

print()
print(f"{F} FAILURE(S)" if F else "All structural checks passed.")
sys.exit(1 if F else 0)
