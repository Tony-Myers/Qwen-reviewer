#!/usr/bin/env python3
"""
Covers the multi-pass merge, the evidence-echo detector and the reliability
banner.

The merge exists because findings rotate: the same paper, the same code and the
same model, two and a half hours apart, produced six defensible concerns across
two passes with no overlap at all, and the second pass lost a verified
inconsistency the first had found. The two reports below are those runs,
reduced. Merging recovers four distinct concerns from six, deduplicating the
sample-size finding across two quite different phrasings.
"""
import sys, types, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
def _stub(n,**a):
    m=types.ModuleType(n); [setattr(m,k,v) for k,v in a.items()]; sys.modules[n]=m
_stub("docx",Document=object); _stub("openpyxl",load_workbook=lambda *a,**k:None)
root=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(root/"app"))
import review_pipeline as rp

RUN2 = """# Overall synopsis
* Study of training load and injury in 32 swimmers.

# Major strengths
* Strength: Bayesian justification is transparent.
* Evidence: The paper justifies Bayesian methods.

# Directly supported concerns
* Concern: There is a discrepancy in the reported prior scale for fixed effects.
* Severity: Substantive
* Evidence: The narrative states a scale of 3 while the equation specifies 5.
* Why it matters: Priors influence the posterior.
* Concern: The final sample size (N=32) is below the minimum threshold (N=34) suggested by the authors' own simulation study.
* Severity: Substantive
* Evidence: Table 1 gives 22 male and 10 female.
* Why it matters: Credible intervals may be less stable.

# Verification prompts
* Check: Verify whether the models included season or year as a covariate.
* Reason: The two seasons differ in external conditions.

# Extraction limits
* Limit: MCMC diagnostics are not detailed.

# Overall confidence
* Moderate.
"""

RUN3 = """# Overall synopsis
* Study of training load and injury in 32 swimmers.

# Major strengths
* Strength: Diagnostics are comprehensive.
* Evidence: LOOIC and posterior predictive checks are reported.

# Directly supported concerns
* Concern: The use of a null interval of -0.01 to 0.01 for log-odds is extremely narrow.
* Severity: Substantive
* Evidence: The null interval was specified as -0.01 to 0.01.
* Why it matters: Interval width drives the Bayes Factor.
* Concern: With only 32 athletes, the estimation of random effects is likely to be highly uncertain.
* Severity: Substantive
* Evidence: Table 1 gives 22 male and 10 female.
* Why it matters: Few clusters give wide posteriors.
* Concern: The final sample size of 32 falls below the 34 participants the authors' own simulation study suggested.
* Severity: Substantive
* Evidence: The simulation reports 34 participants gives credible precision.
* Why it matters: Precision may be lower than implied.

# Verification prompts
* Check: How did the models account for the lockdown and non-lockdown seasons?
* Reason: A potential confounder.
* Check: How was intuitive training load management by coaches quantified?
* Reason: It is offered as an explanation for the null findings.

# Extraction limits
* Limit: Bayes Factors of 0 are an extraction artefact.

# Overall confidence
* Moderate.
"""

F = 0
def ok(label, cond, detail=""):
    global F
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"   {detail}" if not cond and detail else ""))
    if not cond: F += 1

merged = rp.merge_reports([RUN2, RUN3])
concerns = rp._report_sections(merged).get("directly supported concerns", [])
titles = [rp._CONCERN_RE.match(concerns[b]).group(1)
          for b, _ in rp._concern_groups(concerns)]

print("[merge of the two real runs]")
for t in titles:
    print("   -", t[:88])
print()
ok("both of run 2's concerns survive",
   any("prior scale" in t for t in titles) and any("N=32" in t for t in titles))
ok("run 3's unique concerns are added",
   any("null interval" in t for t in titles) and any("random effects" in t for t in titles))
ok("the duplicate sample-size concern is not added twice",
   sum(1 for t in titles if "34" in t or "N=32" in t) == 1,
   str([t[:40] for t in titles if "34" in t or "N=32" in t]))
ok("five concerns, not six", len(titles) == 4, str(len(titles)))
ok("additions are marked", merged.count("Found only in a later pass.") >= 2)

checks = rp._report_sections(merged).get("verification prompts", [])
check_titles = [rp._CHECK_RE.match(checks[b]).group(1)
                for b, _ in rp._item_groups(checks, rp._CHECK_RE)]
# Lexical matching cannot merge these two phrasings of one question, and a
# threshold loose enough to do so would merge distinct findings. Both surviving
# is the deliberate, safe failure.
ok("both phrasings of the season question survive",
   sum(1 for t in check_titles if "season" in t.lower()) == 2,
   str(check_titles))
ok("the unique coaching check is added",
   any("intuitive" in t for t in check_titles), str(check_titles))

print("\n[the base report's own sections are untouched]")
ok("synopsis is the first pass's", merged.count("# Overall synopsis") == 1)
ok("strengths are the first pass's",
   "Bayesian justification is transparent" in merged
   and "Diagnostics are comprehensive" not in merged)
ok("extraction limits are the first pass's",
   "MCMC diagnostics are not detailed" in merged)

print("\n[degenerate input]")
ok("single report passes through", rp.merge_reports([RUN2]) == RUN2)
ok("empty list is safe", rp.merge_reports([]) == "")
ok("blank drafts ignored", rp.merge_reports([RUN2, "", "   "]) == RUN2)
ok("identical passes add nothing",
   rp.merge_reports([RUN2, RUN2]).count("Found only in a later pass.") == 0)
ok("a malformed pass does not break the merge",
   isinstance(rp.merge_reports([RUN2, "not a report at all"]), str))

print("\n[the duplicate threshold, against the run that set it]")
# Verbatim from the three-pass run whose merged report carried the null-interval
# concern twice. The duplicate pair must merge; every genuinely distinct pair
# must not.
NULL_A = ("The justification for the narrow null interval used in Bayes Factor "
          "calculation is not fully detailed relative to predictor scaling.")
NULL_B = ("The interpretation of Bayes Factors relies on a very narrow null "
          "interval (-0.01 to 0.01) for predictors that are scaled, which may "
          "not align with practical significance thresholds for training load.")
AMBIG = ("Ambiguity in the reported Bayes Factor values hinders verification of "
         "the strength of evidence for the null hypothesis.")
SEASON = ("The study spans two distinct seasons with different external "
          "constraints (lockdowns), but it is unclear if the model accounted "
          "for this temporal heterogeneity.")
ok("the duplicated null-interval concern merges", rp._same_item(NULL_A, NULL_B))
ok("ambiguity vs null interval stays distinct", not rp._same_item(AMBIG, NULL_A))
ok("ambiguity vs the other phrasing stays distinct", not rp._same_item(AMBIG, NULL_B))
ok("seasons vs null interval stays distinct", not rp._same_item(SEASON, NULL_A))
ok("seasons vs the other phrasing stays distinct", not rp._same_item(SEASON, NULL_B))
ok("an item always matches itself", rp._same_item(NULL_A, NULL_A))
ok("empty text never matches", not rp._same_item("", NULL_A))

print("\n[counting items, so validation losses are visible]")
ok("counts the base report", rp.count_report_items(RUN2) == (2, 1),
   str(rp.count_report_items(RUN2)))
ok("counts the second pass", rp.count_report_items(RUN3) == (3, 2),
   str(rp.count_report_items(RUN3)))
ok("counts the merged report", rp.count_report_items(rp.merge_reports([RUN2, RUN3])) == (4, 3),
   str(rp.count_report_items(rp.merge_reports([RUN2, RUN3]))))
ok("an empty report counts as nothing", rp.count_report_items("") == (0, 0))

print("\n[the merge reports what it did]")
stats = {}
rp.merge_reports([RUN2, RUN3], stats=stats)
ok("stats record the pass count", stats.get("passes") == 2, str(stats))
# Two concerns plus two verification prompts: the count spans both merged
# sections, not concerns alone.
ok("stats record what was added across both sections",
   stats.get("added") == 4, str(stats))
single = {}
rp.merge_reports([RUN2], stats=single)
ok("a single pass records one pass, nothing added",
   single == {"passes": 1, "added": 0}, str(single))
agreed = {}
rp.merge_reports([RUN2, RUN2], stats=agreed)
ok("passes that agree record zero additions",
   agreed.get("added") == 0, str(agreed))

print("\n[repeat passes are sampled warmer than the first]")
ok("a repeat temperature is configured", rp.REPEAT_PASS_TEMPERATURE > rp.TEMPERATURE,
   f"{rp.REPEAT_PASS_TEMPERATURE} vs {rp.TEMPERATURE}")
ok("the default sampler is unchanged",
   rp.make_default_sampler().temperature == rp.TEMPERATURE)
ok("an override is honoured",
   rp.make_default_sampler(0.7).temperature == 0.7)

print("\n[evidence that merely restates the concern]")
ECHO = """# Directly supported concerns
* Concern: The null interval of -0.01 to 0.01 is extremely narrow and may classify trivially small effects as non-null.
* Severity: Substantive
* Evidence: The file synopsis states: The null interval of -0.01 to 0.01 is extremely narrow and may classify trivially small effects as non-null.
* Why it matters: Interval width drives the Bayes Factor.

# Verification prompts
* Check: something.
"""
ok("an echoed evidence line is flagged", len(rp.evidence_echo_problems(ECHO)) == 1)
ok("it drives confidence to Low",
   rp.concern_confidence(ECHO, "unrelated source")[0] == "Low")
ok("the reason names the echo",
   "restates the concern" in rp.concern_confidence(ECHO, "unrelated source")[1])
ok("a genuine evidence line is not flagged", rp.evidence_echo_problems(RUN2) == [])
ok("a report with no concerns is safe",
   rp.evidence_echo_problems("# Overall synopsis\n* x") == [])

print("\n[reliability banner]")
all_low = rp.annotate_concern_confidence(ECHO, "unrelated source")
ok("banner appears when nothing is High",
   "No concern in this report is supported" in rp.report_reliability_banner(all_low))
ok("no banner once a concern is High",
   rp.report_reliability_banner(all_low.replace("Confidence: Low", "Confidence: High", 1)) == "")
ok("no banner without confidence lines",
   rp.report_reliability_banner("# Overall synopsis\n* x") == "")
ok("no banner on empty input", rp.report_reliability_banner("") == "")

print()
if F:
    print(f"{F} FAILURE(S)"); sys.exit(1)
print("All merge and echo checks passed.")
