#!/usr/bin/env python3
"""
One unusable methodology judgement must not withhold an answer.

    python3 tests/test_academic_methodology_assessment_failure.py

Reproduces the live failure of 1 October 2026 ("What is Rubin's relative
efficiency formula for multiple imputation, and what does it imply about the
number of imputations?"). The answer was withheld with "Academic
methodological checking could not be completed." The schema fixes the
judge's fields and status, so the remaining contract the model could break
is the reason of no more than 30 words: one verbose reason aborted the whole
request.

Run through the real claim-coverage pipeline, release assessment,
reconciliation lifecycle, evidence layer (with the real reviewer notes) and
endpoint. Only the model calls are replaced. Checked:

  1. an over-long reason, or output the assessor cannot decode, makes that
     claim "not established" instead of failing the request;
  2. the failure is kept for diagnostics and written to the server log;
  3. the answer is presented, and is not reported as a concern;
  4. backend failures and application-owned input errors still raise.
"""
import asyncio
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat                          # noqa: E402
import academic_check_further as cf           # noqa: E402
import academic_claim_assessor                # noqa: E402
import academic_claim_coverage as coverage    # noqa: E402
import academic_methodology as am             # noqa: E402
import academic_orchestrator as orchestrator  # noqa: E402
import academic_reconciliation as reconciliation                      # noqa: E402
import academic_reconciliation_orchestrator as lifecycle              # noqa: E402
import academic_technical                     # noqa: E402
import server                                 # noqa: E402
from llm_backend import BackendError          # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


QUESTION = ("What is Rubin's relative efficiency formula for multiple "
            "imputation, and what does it imply about the number of "
            "imputations?")
FORMULA_SENTENCE = ("The relative efficiency of m imputations is "
                    "approximately 1 / (1 + FMI/m).")
COUNT_SENTENCE = ("More imputations are needed when the fraction of missing "
                  "information is high.")
ANSWER = FORMULA_SENTENCE + " " + COUNT_SENTENCE
FORMULA = "Relative efficiency is approximately 1 / (1 + FMI/m)."
FORMULA_ANCHOR = "relative efficiency of m imputations is approximately 1 / (1 + FMI/m)"
COUNT = ("More imputations are needed when the fraction of missing "
         "information is high.")
COUNT_ANCHOR = ("imputations are needed when the fraction of missing "
                "information is high")
LONG_REASON = " ".join(["word"] * 31)


def coverage_model(*, prompt, schema):
    if schema == coverage.claim_discovery_output_schema() and "ANSWER DRAFT" in prompt:
        return {"discovered_claims": [
            {"type": "formula", "concept": "relative efficiency",
             "statement": FORMULA, "parameterisation": None,
             "source_anchor": FORMULA_ANCHOR},
            {"type": "interpretation", "concept": "number of imputations",
             "statement": COUNT, "parameterisation": None,
             "source_anchor": COUNT_ANCHOR},
        ]}
    if schema == coverage.claim_discovery_output_schema():
        return {"discovered_claims": []}
    if schema == coverage.claim_decomposition_output_schema():
        return {"requires_decomposition": False, "atomic_claims": []}
    if schema == coverage.claim_representation_output_schema():
        return {"represented": False, "represented_by": None}
    raise AssertionError("unexpected schema")


def coverage_assessor(*, answer_draft, existing_claims):
    return coverage.ClaimCoverageAssessment.from_result(
        coverage.assess_claim_coverage_two_stage(
            answer_draft=answer_draft, existing_claims=existing_claims,
            assessor=coverage_model))


def restriction_assessor(*, prompt, schema):
    # Every occurrence is judged to lose context, so the contextual judge
    # runs as well as the standalone one.
    return {"material_restriction_omitted": True}


judge_calls = []


def methodology_judge(*, prompt, schema):
    """The live failure: a reason over 30 words, or undecodable output."""
    judge_calls.append(prompt)
    if FORMULA in prompt:
        return {"status": "methodologically_consistent", "reason": LONG_REASON}
    raise academic_claim_assessor.ClaimAssessorOutputError(
        "Claim assessor did not return valid JSON.")


def first_stage(judge):
    draft = academic_chat.AcademicDraft(
        answer_draft=ANSWER, references=[], source_claims=[], technical_claims=[])
    return orchestrator.assess_academic_draft(
        draft,
        local_guidance=orchestrator.retrieve_methodological_context(QUESTION),
        technical_verifier=academic_technical.verify_technical_claim,
        methodological_assessor=judge,
        claim_methodological_retriever=orchestrator.retrieve_methodological_context,
        coverage_assessor=coverage_assessor,
        material_restriction_assessor=restriction_assessor,
    )


def must_not_revise(*args, **kwargs):
    raise AssertionError("An unusable judgement must not trigger a revision.")


# ===========================================================================
print("\n[1] unusable judgements become 'not established'")
log = io.StringIO()
with contextlib.redirect_stderr(log):
    checked = first_stage(methodology_judge)

standalone = [t.methodological_consistency for t in checked.technical_claims
              if t.methodological_consistency is not None]
contextual = [a.contextual_methodological_consistency
              for a in checked.discovered_claim_assessments
              if a.contextual_methodological_consistency is not None]
results = standalone + contextual
check(bool(judge_calls) and bool(standalone) and bool(contextual),
      f"both standalone and contextual judges ran ({len(standalone)} + "
      f"{len(contextual)} judgements)")
check(all(r.status == am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED for r in results),
      "every unusable judgement is 'not established'")
check(all(r.reasons == [am.METHODOLOGICAL_ASSESSMENT_NOT_COMPLETED_REASON]
          for r in results),
      "the model's verbose reason is not passed on")
check(any("30 words" in r.assessment_error for r in results)
      and any("ClaimAssessorOutputError" in r.assessment_error for r in results),
      "the underlying error is kept: the 30-word limit and the decode failure")

# ===========================================================================
print("\n[2] the failure reaches diagnostics and the server log")
first = checked.technical_claims[0].to_dict()
check("assessment_error" in first["methodological_consistency"],
      "standalone result: assessment_error appears in its dictionary")
ctx = next(a.to_dict() for a in checked.discovered_claim_assessments
           if a.contextual_methodological_consistency is not None)
check("assessment_error" in ctx["contextual_methodological_consistency"],
      "contextual result: assessment_error appears in its dictionary")
logged = log.getvalue()
check("[methodology] check not completed" in logged and "30 words" in logged,
      "the server log records the claim and the error")
ok = am.MethodologicalConsistencyResult(
    status=am.METHODOLOGICAL_STATUS_CONSISTENT, claim=standalone[0].claim,
    passages=standalone[0].passages, reasons=["Fine."])
check("assessment_error" not in ok.to_dict(),
      "a completed judgement's dictionary is unchanged")

# ===========================================================================
print("\n[3] the answer is presented and not treated as a concern")
check(checked.release.safe_to_present is True
      and checked.release.status != orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
      "release: presentable, with no methodological conflict recorded "
      f"({checked.release.status})")
reconciled = lifecycle.run_academic_reconciliation(
    object(), object(), QUESTION,
    first_stage_runner=lambda *args: checked,
    correction_extractor=reconciliation.extract_academic_corrections,
    revision_generator=must_not_revise,
    draft_assessor=must_not_revise)
check(reconciled.revision_attempted is False and reconciled.final is checked,
      "no revision: the original answer is the one presented")
evidence = cf.assess_check_further(
    reconciled.final, orchestrator.methodological_notes_index()).to_dict()
check(evidence["state"] != "worth_checking" and evidence["worth_checking"] == [],
      f"the reader is not told it is worth checking ({evidence['state']})")

with contextlib.redirect_stderr(io.StringIO()):
    original = (server.ensure_model,
                server.academic_reconciliation_orchestrator.run_academic_reconciliation)
    server.ensure_model = lambda: None
    server.academic_reconciliation_orchestrator.run_academic_reconciliation = (
        lambda *a, **k: reconciled)
    try:
        payload = asyncio.run(server.academic_chat_first_stage({"question": QUESTION}))
    finally:
        (server.ensure_model,
         server.academic_reconciliation_orchestrator.run_academic_reconciliation) = original
check(isinstance(payload, dict) and payload["release"]["safe_to_present"] is True
      and payload["answer_draft"] == ANSWER,
      "endpoint: the answer is returned instead of a 502")

# ===========================================================================
print("\n[4] other failures still raise")
claim = standalone[0].claim
passages = standalone[0].passages


def backend_down(*, prompt, schema):
    raise BackendError("No llama-server is listening.")


try:
    am.assess_methodological_consistency(claim, passages, backend_down)
except BackendError:
    check(True, "a backend failure still propagates")
else:
    check(False, "a backend failure still propagates")


def fine(*, prompt, schema):
    return {"status": "methodologically_consistent", "reason": "Fine."}


try:
    with contextlib.redirect_stderr(io.StringIO()):
        am.assess_methodological_consistency(claim, [], fine)
except am.MethodologicalAssessmentOutputError:
    check(False, "missing passages are an application error, not model output")
except ValueError:
    check(True, "missing passages still raise as an application error")
else:
    check(False, "missing passages still raise as an application error")

try:
    am.build_methodological_consistency(
        claim, passages, {"status": "methodologically_consistent",
                          "reason": LONG_REASON})
except am.MethodologicalAssessmentOutputError:
    check(True, "the validator itself is unchanged: it still rejects the output")
else:
    check(False, "the validator itself is unchanged: it still rejects the output")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
