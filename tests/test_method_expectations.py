#!/usr/bin/env python3
"""
Checks on tests/method_expectations.py.

Every negative case here was a real fault. The passages are quoted from the
documents in inputs/, because section 12.1 of reports/DESIGN-EXPECTATIONS.md
recorded four faults that synthetic passages had not exposed, and one test
that had passed for the wrong reason.

    python3 tests/test_method_expectations.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import method_expectations as me   # noqa: E402

PASS, FAIL = 0, 0


def check(label: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


def present(check_fn, text: str) -> bool:
    return check_fn(me.de.normalise_extraction(text)).kind == "present"


# ---------------------------------------------------------------------------
# Priors
# ---------------------------------------------------------------------------
print("priors")

# Myers et al. 2020. The first pattern listed prior families and missed both
# of these, reporting a paper that states its priors as having none.
check("jeffrey's prior on sigma",
      present(me._check_priors,
              "this initial model was fitted using a jeffrey's prior on sigma "
              "and a zellner-siow cauchy prior on model coefficients"))
check("zellner-siow cauchy prior",
      present(me._check_priors, "a zellner-siow cauchy prior on model coefficients"))

# Eustace et al. 2025 and the training-load paper.
check("student-t prior for the intercept",
      present(me._check_priors,
              "the prior for the intercept was a student-t distribution with 3 "
              "degrees of freedom"))
check("prior distributions declared",
      present(me._check_priors,
              "2. prior distributions: sigma ~ student t(3, 0, 2.5)"))
check("prior predictive checks",
      present(me._check_priors,
              "to determine whether these priors were appropriate, prior "
              "predictive checks were performed"))
# The plural after "to" is an infinitive, not the preposition. The first
# exclusion list read "different priors to examine" as ordinary English.
check("different priors to examine",
      present(me._check_priors,
              "a series of bayesian models were also fitted with different "
              "priors to examine the potential influence of measurement error"))
check("uniform and informative priors",
      present(me._check_priors,
              "ranging from uniform priors to increasingly informative priors"))

# RJSP-2026-0327. All eight occurrences of "prior" in 127 pages are these.
for ordinary in [
    "based on prior research and the distribution of available data",
    "the posterior distribution of effects based on both sample data and prior "
    "information, offering cris in place of confidence intervals",
    "prior to modeling, the intervention network was evaluated",
    "our study, in contrast to prior approaches, employed bayesian hierarchical modeling",
    "participants gave written informed consent prior to any testing commencing",
    "murayama demonstrated that prior use of a lawyer was a key predictor",
    "one week prior to the winter championship",
]:
    check(f"ordinary English: {ordinary[:44]}...",
          not present(me._check_priors, ordinary))


# ---------------------------------------------------------------------------
# Convergence
# ---------------------------------------------------------------------------
print("convergence")

# Three encodings of R-hat reach the text layer across this corpus. Matching
# only the spelled form reported two of the three as missing.
check("r-hat spelled (Eustace et al. 2025)",
      present(me._check_convergence,
              "all models were checked for convergence (r-hat = 1)"))
check("r with a combining circumflex (Myers et al. 2020)",
      present(me._check_convergence,
              "all models reported were checked for convergence (r̂ = 1)"))
check("r, space, combining circumflex (Cullen et al.)",
      present(me._check_convergence,
              "all models were checked for convergence (r ̂ = 1)"))
check("effective sample size",
      present(me._check_convergence, "the effective sample size exceeded 1000"))
check("trace plots",
      present(me._check_convergence, "convergence was assessed by trace plots"))

# The bare claim. RJSP-2026-0327 says exactly this and reports no statistic
# anywhere in 127 pages.
check("a claim of convergence is not a diagnostic",
      not present(me._check_convergence,
                  "with stable convergence and favorable model performance (52)"))
# Extraction splits words: "str ess" and "ass ess" both occur in inputs/.
check("split words do not match ESS",
      not present(me._check_convergence,
                  "autonomic regulation contributes to exercise str ess and "
                  "post-exercise re-equilibration"))
check("bayesian and frequentist estimates converge",
      not present(me._check_convergence,
                  "large enough for the bayesian and frequentist estimates to "
                  "converge on the same conclusions"))


# ---------------------------------------------------------------------------
# Sampler settings
# ---------------------------------------------------------------------------
print("sampler settings")

check("four chains of 2000 iterations",
      present(me._check_sampler, "four chains of 2,000 iterations were run"))
check("chains = 4",
      present(me._check_sampler, "chains = 4, iter = 4000"))
check("burn-in of 5000",
      present(me._check_sampler, "a burn-in of 5,000 was discarded"))
check("thinning of 10",
      present(me._check_sampler, "with a thinning interval of 10"))

# The trap. Three occurrences of "warm-up" in RJSP-2026-0327 and several more
# across inputs/, every one of them the exercise warm-up.
check("exercise warm-up is not a sampler setting",
      not present(me._check_sampler,
                  "the duration of the main exercise phase per session "
                  "(excluding warm-up and cool-down)"))
check("prescribed warm-up activities",
      not present(me._check_sampler,
                  "the teacher performed a joint warm-up before each assessment "
                  "section (there are prescribed warm-up activities)"))
# "sample size" is not a sampler setting. On RPAN-2024-0733 the pattern matched
# "a larger 81 sample size", where 81 is a marginal line number left glued to
# the text; the MBI paper supplies three more. This is a false PRESENT, which
# suppresses a true absence rather than creating a false one.
check("a line number beside sample size is not a sampler setting",
      not present(me._check_sampler,
                  "which provides a larger 81 sample size and allows for more "
                  "accurate conclusions"))
check("ordinary sentences about sample size do not count",
      not present(me._check_sampler,
                  "when the standard error is large enough, for example when the "
                  "sample size is very small"))
check("5000 retained samples still counts",
      present(me._check_sampler, "we retained 5000 samples per chain"))

check("markov chain is not a chain count",
      not present(me._check_sampler,
                  "to implement a hamiltonian markov chain monte carlo with a "
                  "no-u-turn sampler"))
check("warm-up of 1000 iterations is a sampler setting",
      present(me._check_sampler, "a warm-up of 1000 iterations was discarded"))


# ---------------------------------------------------------------------------
# Software
# ---------------------------------------------------------------------------
print("software")

check("brms and Stan",
      present(me._check_software,
              "fitted using the bayesian regression models using stan (brms) package"))
check("MBNMAdose and gemtc",
      present(me._check_software,
              "implemented using the mbnmadose package; network meta-regression "
              "was conducted using the gemtc package"))
check("MLwiN",
      present(me._check_software,
              "modeled using markov chain monte carlo methods within mlwin"))
# Extraction splits "gold standard" into "gold stan - dard" in Eustace et al.
check("gold stan - dard is not Stan",
      not present(me._check_software,
                  "isokinetic dynamometry offers the gold stan - dard method"))


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------
print("gate")

check("two strong signals plus evidence of running open the gate",
      me.bayesian_gate("credible intervals were computed from the posterior "
                       "distribution; the model was fitted in brms").fired)
# Two strong signals are no longer sufficient on their own. Nothing here says
# an analysis was run.
check("two strong signals alone no longer open the gate",
      not me.bayesian_gate("credible intervals were computed from the posterior "
                           "distribution").fired)
check("one weak signal alone does not",
      not me.bayesian_gate("a bayesian approach has been suggested elsewhere").fired)
check("a bare mention does not open the gate",
      not me.bayesian_gate("we used ordinary least squares regression").fired)
# The gate must not be carried by the ordinary-English "prior" that carries
# MethodClass on RJSP-2026-0327.
check("ordinary-English prior does not open the gate",
      not me.bayesian_gate("in contrast to prior approaches, hierarchical "
                           "modeling was used").fired)
# ROPE is guarded: "rope skipping" appears in a reference title in inputs/.
# The MBI critique (RJSP-2020-1136) opened the first gate on three strong
# signals and fits no model. Each sentence below is quoted from it.
MBI = ("statisticians have called for mbi users to replace it with a fully "
       "bayesian analysis, or to use standard frequentist methods. we note that "
       "mbi has been presented as a bayesian method with a weakly informative "
       "prior. report p-values numerically; do not interpret them as bayesian "
       "posterior probabilities within a frequentist analysis. the data can be "
       "analysed using standard statistical software by running a one-sided "
       "test. when the sample size is very small it is not possible to find "
       "statistical equivalence.")
mbi_gate = me.bayesian_gate(MBI)
check("a paper arguing about Bayesian methods reaches two strong signals",
      len(mbi_gate.strong) >= 2)
check("but nothing shows an analysis was run", not mbi_gate.doing)
check("so the gate stays closed", not mbi_gate.fired)

# The narrowest true case: the body-size paper names no software, reports no
# diagnostic and gives no numeric interval. Only the fitting statement keeps it.
BODY_SIZE = ("a series of bayesian models were also fitted to the physical "
             "fitness test-dependent variables with different priors to examine "
             "the potential influence of measurement error. the bayesian models "
             "provide a full posterior distribution of the predictions.")
body_gate = me.bayesian_gate(BODY_SIZE)
check("a statement that models were fitted is evidence of running",
      "a statement that a model was fitted" in body_gate.doing)
check("so the body-size paper still opens the gate", body_gate.fired)

check("rope skipping does not open the gate",
      not me.bayesian_gate("open feedback on conformity among judges in rope "
                           "skipping. psychol. sport exerc.").fired)


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------
print("methods scope")

STRUCTURED_ABSTRACT = (
    "Abstract: Objective: This study explores how exercise modalities affect "
    "cognitive flexibility using Bayesian network meta-analysis.\n"
    "Methods: A literature search identified randomized controlled trials "
    "across six databases. Data were analyzed using the MBNMAdose package in R.\n"
    "Results: A total of 76 studies involving 6,047 older adults were included.\n"
    "Discussion: The findings suggest a nonlinear relationship.\n"
    "1 Introduction\n"
    "Cognitive decline is a growing concern.\n"
    "2 Methods\n"
    "2.1 Protocol and registration\n"
    "The review followed PRISMA-NMA. Bayesian network meta-analysis was "
    "performed with credible intervals and DIC reported.\n"
    "3 Results\n"
    "A total of 76 studies were included.\n"
)

scope = me.methods_scope(STRUCTURED_ABSTRACT)
check("scope is found", scope.text is not None)
check("scope skips the abstract",
      scope.text is not None and "literature search identified" not in scope.text)
check("scope reaches the real methods",
      scope.text is not None and "PRISMA-NMA" in scope.text)
check("scope stops at the results heading",
      scope.text is not None and "A total of 76 studies were included." not in scope.text)
check("no methods heading returns None",
      me.methods_scope("A short note with no sections at all.").text is None)


print(f"\n{PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
