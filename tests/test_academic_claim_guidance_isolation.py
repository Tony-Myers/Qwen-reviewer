#!/usr/bin/env python3
"""
Each claim is judged only against guidance retrieved for that claim.

    python3 tests/test_academic_claim_guidance_isolation.py

Commit 1b90b35 (26 September 2026) stopped reusing the guidance retrieved
for the question when judging individual claims. Its tests assert the rule
with synthetic markers only. This test shows, with the real reviewer notes
and no model output, what the rule protects.

A question about multiple imputation retrieves Missing Data sections. An
answer may also make a claim the question did not ask about -- here, on
divergent transitions in Hamiltonian Monte Carlo. If question-level
guidance were added to every claim's guidance:

  1. the judge would be handed the multiple-imputation sections for the
     HMC claim, guidance that is irrelevant to it (the "irrelevant
     retrieved passage" and "same topic, different proposition" boundaries
     in tests/probe_academic_methodology_conflicts.py); and
  2. the evidence layer, which offers further reading only for a point
     "judged against a curated section retrieved for the question", would
     route the HMC point to multiple-imputation reading, because every
     judgement would then include the question's sections.

Only the model calls are replaced; the judge returns "not established"
for every claim, so nothing here depends on stochastic output.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat                          # noqa: E402
import academic_check_further as cf           # noqa: E402
import academic_methodology as am             # noqa: E402
import academic_orchestrator as orchestrator  # noqa: E402
import academic_technical                     # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


QUESTION = ("What is Rubin's relative efficiency formula for multiple "
            "imputation, and what does it imply about the number of "
            "imputations?")
ON_TOPIC = academic_chat.TechnicalClaim(
    type="formula", concept="relative efficiency",
    statement=("The relative efficiency of m imputations is approximately "
               "1 / (1 + FMI/m)."),
    parameterisation=None)
OFF_TOPIC = academic_chat.TechnicalClaim(
    type="diagnostic", concept="divergent transitions",
    statement=("Divergent transitions in Hamiltonian Monte Carlo indicate "
               "problematic posterior geometry."),
    parameterisation=None)
ANSWER = ON_TOPIC.statement + " " + OFF_TOPIC.statement
MISSING_DATA = "Missing Data, Dropout and Analysis Populations"

prompts = {}


def judge(*, prompt, schema):
    key = "off" if OFF_TOPIC.statement in prompt else "on"
    prompts[key] = prompt
    return {"claim_proposition": "Synthetic claim proposition.",
            "guidance_proposition": "Synthetic guidance proposition.",
            "relationship": 'insufficient',
            "reason": "Synthetic deterministic judgement."}


question_guidance = orchestrator.retrieve_methodological_context(QUESTION)
result = orchestrator.assess_academic_draft(
    academic_chat.AcademicDraft(answer_draft=ANSWER, references=[],
                                source_claims=[],
                                technical_claims=[ON_TOPIC, OFF_TOPIC]),
    local_guidance=question_guidance,
    technical_verifier=academic_technical.verify_technical_claim,
    methodological_assessor=judge,
    claim_methodological_retriever=orchestrator.retrieve_methodological_context,
)

print("\n[0] the fixture: the question retrieves only Missing Data guidance")
check(question_guidance.passages
      and all(p.note == MISSING_DATA for p in question_guidance.passages),
      "question guidance: " + "; ".join(p.heading for p in question_guidance.passages))

by_statement = {t.claim.statement: t.methodological_consistency
                for t in result.technical_claims}
off = by_statement[OFF_TOPIC.statement]
on = by_statement[ON_TOPIC.statement]

print("\n[1] the off-topic claim is judged against its own guidance only")
check(on is not None and any(p.note == MISSING_DATA for p in on.passages),
      "the on-topic claim retrieves Missing Data guidance by itself")
check(off is not None and all(p.note != MISSING_DATA for p in off.passages),
      "the HMC claim is not given the question's Missing Data sections: "
      + "; ".join(f"{p.note} - {p.heading}" for p in (off.passages if off else [])))
mi_text = next(p.text for p in question_guidance.passages
               if p.heading == "How does FMI affect relative efficiency?")
check("off" in prompts and mi_text[:120] not in prompts["off"],
      "the judge's prompt for the HMC claim contains no Missing Data text")

print("\n[2] further reading is offered only where the point was judged")
evidence = cf.assess_check_further(
    result, orchestrator.methodological_notes_index()).to_dict()
routing = {r["statement"]: r["routed_to"]
           for r in evidence["diagnostics"]["routing"]}
check(routing.get(OFF_TOPIC.statement) is None,
      "the HMC point is not routed to multiple-imputation reading "
      f"(routed to: {routing.get(OFF_TOPIC.statement)})")
check((routing.get(ON_TOPIC.statement) or "").startswith(MISSING_DATA),
      "the relative-efficiency point is routed to Missing Data reading "
      f"(routed to: {routing.get(ON_TOPIC.statement)})")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
