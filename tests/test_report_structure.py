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
    ok("item table renders", "# Items by evidence" in table)
    # Ordered by what the citation check found, not by a grade the synthesis
    # awarded itself. The severity label used one of its three values for 82%
    # of concerns and, when it did discriminate, ranked its best-supported
    # concern below its weakest.
    ok("a concern whose quotations verify is Verified", "| Verified |" in table)
    ok("one resting on the pipeline's own summary is Unverified",
       "| Unverified |" in table)
    ok("a verification prompt is a Question", "| Question |" in table)
    ok("the table does not claim to rank importance",
       "does not rank importance" in table)
    ok("Verified sorts above Unverified",
       table.index("| Verified |") < table.index("| Unverified |"))
    lines = [l for l in table.splitlines() if l.startswith("| ") and "---" not in l]
    ok("one header + four items", len(lines) == 5, str(len(lines)))
    ok("the verified concern sorts first",
       lines[1].startswith("| Verified |"), lines[1][:40])

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

# A thinking-mode run wrote every field of a concern on one line. The table then
# carried the whole paragraph as the item, and defaulted every row to High
# because no line carried the fields it expected. A stray "Severity:" left over
# from an older prompt must still be trimmed out of the item text.
_ONE_LINE = ("# Directly supported concerns\n"
             "- Concern: The prior specification needs clarification. Severity: "
             "Substantive. Evidence: the prior is a Student's t. Why it matters: "
             "it should be positive.\n"
             "* Confidence: High — every quotation was located.\n\n"
             "- Concern: The ACWR calculation could be clarified. Evidence: a "
             "decay constant in days.\n"
             "* Confidence: Moderate — an inference.\n\n"
             "# Verification prompts\n"
             "- Check: whether season was modelled. Reason: it spans two seasons.\n")
_table = rp.format_action_list(_ONE_LINE)
ok("a run-together concern is cut at the next field",
   "| Verified | The prior specification needs clarification |" in _table, _table)
ok("a stray severity label does not reach the item text",
   "Severity" not in _table, _table)
ok("its own confidence still places it",
   "| Inferred | The ACWR calculation could be clarified |" in _table, _table)
ok("a run-together check drops its reason",
   "| Question | Whether season was modelled |" in _table, _table)
ok("the field-per-line form still works",
   "| Verified | Something is wrong. |" in rp.format_action_list(
       "# Directly supported concerns\n* Concern: Something is wrong.\n"
       "Evidence: The text states, \"a quotation\".\n"
       "* Confidence: High — every quotation was located.\n"))
ok("clean report yields no overclaims", rp.overclaim_problems("A measured statement.") == [])

print("\n[an unfinished synthesis is refused, not published]")
# A thinking-mode synthesis spent 9,800 of its 10,000 tokens reasoning and
# stopped four words into a sentence. Two headings and half a strength arrived,
# perfectly formatted, and every check downstream passed them.
_CUT = ("# Overall synopsis\n- Something.\n\n# Major strengths\n"
        "- Strength: Posterior summaries are reported. Evidence: The table "
        "reports log odds, credible intervals, odds ratios, and Bayes\n")
_FULL = ("# Overall synopsis\n- Something.\n\n# Directly supported concerns\n"
         "* Concern: A thing.\n\n# Overall confidence\n* Moderately confident.\n")
ok("a report that never reaches its last heading is caught",
   "never reached its final" in rp.report_looks_truncated(_CUT))
ok("a complete report passes", rp.report_looks_truncated(_FULL) == "",
   rp.report_looks_truncated(_FULL))
ok("an empty one is caught too",
   "returned nothing" in rp.report_looks_truncated(""))
ok("a mid-sentence ending is caught even with every heading present",
   "mid-sentence" in rp.report_looks_truncated(
       _FULL.rstrip() + "\n* and the last point breaks off here mid"))
ok("a table or heading ending is not mistaken for one",
   rp.report_looks_truncated(_FULL.rstrip() + "\n| High | An action |") == "")

server_src_2 = (ROOT / "app" / "server.py").read_text()
ok("the server refuses to write one",
   "rp.report_looks_truncated(final_report)" in server_src_2)

print("\n[the version stamp covers every file that shapes a review]")
import hashlib
_app = Path(rp.__file__).resolve().parent
_expected = hashlib.sha1(
    (_app / "review_pipeline.py").read_bytes()
    + (_app / "server.py").read_bytes()
    + (_app / "llm_backend.py").read_bytes()
).hexdigest()[:8]
ok("the stamp hashes all three files that shape a review",
   rp.PIPELINE_VERSION == _expected, f"{rp.PIPELINE_VERSION} vs {_expected}")
ok("a server-only edit would change the stamp",
   rp._fingerprint_of(_app / "review_pipeline.py") != rp.PIPELINE_VERSION)
ok("so would a backend-only edit, where the sampler and thinking mode live",
   rp._fingerprint_of(_app / "review_pipeline.py",
                      _app / "server.py") != rp.PIPELINE_VERSION)
ok("the stale check uses the same inputs", rp.stale_module_warning() == "",
   rp.stale_module_warning()[:80])
ok("a missing file is reported, not guessed",
   rp._fingerprint_of(_app / "no_such_file.py") == "unknown")

print()
print(f"{F} FAILURE(S)" if F else "All structural checks passed.")
sys.exit(1 if F else 0)
