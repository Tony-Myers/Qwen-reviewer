#!/usr/bin/env python3
"""
A semantic methodological conflict is evidence, not release authority.

    python3 tests/test_academic_methodological_release_authority.py

Reproduces the live failure of 1 October 2026 ("Does a non-significant result
mean there is no effect?"). The answer said, correctly:

    A common misconception is that 'absence of evidence is evidence of
    absence'; however, failure to obtain statistical significance usually
    indicates uncertainty rather than proof that no effect exists.

Claim discovery quoted the rejected proposition as if it were asserted, giving
the atomic claim "Absence of evidence is evidence of absence." The restriction
check correctly found that material context was lost, the contextual
methodology judge received the verified sentence (misconception label and
all) and still returned methodological_conflict, and that one semantic verdict
withheld a correct answer.

Run here through the real claim-coverage pipeline, release assessment,
reconciliation lifecycle, correction extractor, evidence layer (with the real
reviewer notes) and endpoint. Only the model calls are replaced, each
returning what the live run produced. Checked:

  1. the answer stays presentable and is not revised;
  2. the conflict is kept as evidence and shown as "Worth checking", quoting
     the application-owned answer sentence and naming the local guidance;
  3. deterministic technical conflicts and source contradictions still
     withhold the answer, and only they become correction material;
  4. "not established" stays non-blocking, and incomplete checking stays
     distinct from a concern about the answer.
"""
import asyncio
import contextlib
import copy
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat                          # noqa: E402
import academic_check_further as cf           # noqa: E402
import academic_claim_coverage as coverage    # noqa: E402
import academic_claims                        # noqa: E402
import academic_methodology                   # noqa: E402
import academic_orchestrator as orchestrator  # noqa: E402
import academic_reconciliation as reconciliation                      # noqa: E402
import academic_reconciliation_orchestrator as lifecycle              # noqa: E402
import academic_technical                     # noqa: E402
import server                                 # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


QUESTION = "Does a non-significant result mean there is no effect?"
SENTENCE = ("A common misconception is that 'absence of evidence is evidence "
            "of absence'; however, failure to obtain statistical significance "
            "usually indicates uncertainty rather than proof that no effect "
            "exists.")
ANSWER = ("No. A non-significant result does not show that there is no effect. "
          + SENTENCE +
          " Demonstrating the absence of an important effect requires methods "
          "designed for that purpose, such as equivalence testing.")
REJECTED = "Absence of evidence is evidence of absence."
REJECTED_ANCHOR = "absence of evidence is evidence of absence"
SUPPORTED = ("Failure to obtain statistical significance usually indicates "
             "uncertainty rather than proof that no effect exists.")
SUPPORTED_ANCHOR = ("failure to obtain statistical significance usually "
                    "indicates uncertainty rather than proof that no effect exists")


# ---- the model calls, as the live run answered them ----------------------
def coverage_model(*, prompt, schema):
    if schema == coverage.claim_discovery_output_schema() and "ANSWER DRAFT" in prompt:
        return {"discovered_claims": [
            {"type": "interpretation", "concept": "absence of evidence",
             "statement": REJECTED, "parameterisation": None,
             "source_anchor": REJECTED_ANCHOR},
            {"type": "interpretation", "concept": "non-significance",
             "statement": SUPPORTED, "parameterisation": None,
             "source_anchor": SUPPORTED_ANCHOR},
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
    # The restriction layer was right: the misconception label was lost.
    return {"material_restriction_omitted": REJECTED in prompt}


judge_prompts = []


def methodology_judge(*, prompt, schema):
    judge_prompts.append(prompt)
    if REJECTED in prompt:
        return {"status": "methodological_conflict",
                "reason": "The guidance says absence of evidence is not "
                          "evidence of absence."}
    return {"status": "methodologically_consistent",
            "reason": "The guidance states this directly."}


def first_stage():
    draft = academic_chat.AcademicDraft(
        answer_draft=ANSWER, references=[], source_claims=[], technical_claims=[])
    return orchestrator.assess_academic_draft(
        draft,
        local_guidance=orchestrator.retrieve_methodological_context(QUESTION),
        technical_verifier=academic_technical.verify_technical_claim,
        methodological_assessor=methodology_judge,
        claim_methodological_retriever=orchestrator.retrieve_methodological_context,
        coverage_assessor=coverage_assessor,
        material_restriction_assessor=restriction_assessor,
    )


def must_not_revise(*args, **kwargs):
    raise AssertionError("A methodological conflict must not trigger a revision.")


def must_not_reassess(*args, **kwargs):
    raise AssertionError("A methodological conflict must not trigger a reassessment.")


# ===========================================================================
print("\n[1] the live failure: the answer is presented and not revised")
checked = first_stage()
rejected = next(a for a in checked.discovered_claim_assessments
                if a.discovered_claim.claim.statement == REJECTED)
check(rejected.source_context.source_sentence == SENTENCE,
      "extraction produced the rejected proposition, located in the answer's sentence")
check(rejected.material_restriction.material_restriction_omitted is True,
      "the restriction layer found the lost context")
check(rejected.contextual_methodological_consistency.status
      == academic_methodology.METHODOLOGICAL_STATUS_CONFLICT,
      "the contextual judge still returned a conflict")
check(any("BOUNDED ANSWER CONTEXT" in p and "A common misconception" in p
          for p in judge_prompts),
      "the judge was given the sentence that labels it a misconception")
check(checked.release.status == orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT
      and checked.release.safe_to_present is True,
      "release: presentable, with the methodological conflict recorded")

reconciled = lifecycle.run_academic_reconciliation(
    object(), object(), QUESTION,
    first_stage_runner=lambda *args: checked,
    correction_extractor=reconciliation.extract_academic_corrections,
    revision_generator=must_not_revise,
    draft_assessor=must_not_reassess)
check(reconciled.revision_attempted is False and reconciled.final is checked,
      "no revision: the original answer is the one presented")

# ===========================================================================
print("\n[2] the conflict is kept as evidence and shown as worth checking")
assessment = cf.assess_check_further(
    reconciled.final, orchestrator.methodological_notes_index()).to_dict()
item = assessment["worth_checking"][0] if assessment["worth_checking"] else {}
conflict_headings = {p.heading for p in
                     rejected.contextual_methodological_consistency.passages}
check(assessment["state"] == "worth_checking"
      and assessment["title"] == "Worth checking",
      "the evidence check says 'Worth checking'")
check(item.get("text") == SENTENCE and item.get("kind") == "answer_sentence",
      "it quotes the application-owned answer sentence, not the extracted claim")
check(REJECTED not in json.dumps({k: v for k, v in assessment.items()
                                  if k != "diagnostics"}),
      "the reader never sees the extracted proposition as if the answer asserted it")
check(item.get("topic") in conflict_headings,
      "it names the local guidance the conflict was judged against: "
      + repr(item.get("topic")))
check(len(assessment["worth_checking"]) == 1,
      "only the conflicting sentence is raised, not the supported one")

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
      "endpoint: the answer is returned as presentable")
check(payload["check_further"]["state"] == "worth_checking",
      "endpoint: the evidence check reports it as worth checking")
html = (Path(__file__).resolve().parents[1] / "app" / "chat.html").read_text()
send = html[html.index("async function sendAcademicMessage()"):]
check("data.release?.safe_to_present === false" in send
      and "Answer withheld after checking." in send,
      "page: only an unsafe release is withheld, so this answer is shown")

# ===========================================================================
print("\n[3] deterministic and source gates still withhold, and only they correct")
technical_conflict = orchestrator.TechnicalClaimResult(
    claim=academic_chat.TechnicalClaim(
        type="formula", concept="relative efficiency",
        statement="RE = 1 + lambda/M", parameterisation=None),
    verification=academic_technical.TechnicalVerification(
        status=academic_technical.TECHNICAL_STATUS_CONFLICT,
        verifier="mi_relative_efficiency", canonical_claim="RE = 1 / (1 + lambda/M)",
        reasons=["Deterministic conflict."]))
release = orchestrator.assess_academic_release(
    checked.technical_claims + [technical_conflict], checked.source_claims,
    checked.discovered_claim_assessments, checked.claim_coverage)
check(release.status == "blocked_technical_conflict" and release.safe_to_present is False,
      "a deterministic technical conflict still withholds the answer")
corrections = reconciliation.extract_academic_corrections(
    technical_claims=checked.technical_claims + [technical_conflict],
    source_claims=checked.source_claims,
    discovered_claim_assessments=checked.discovered_claim_assessments)
check(len(corrections.technical) == 1 and not corrections.methodological
      and not corrections.contextual_methodological,
      "revision receives the technical correction and no methodological one")

source_claim = academic_chat.SourceClaim(
    claim="The trial showed no effect.", reference_index=0)
contradicted = object.__new__(orchestrator.SourceClaimResult)
contradicted.claim = source_claim
for name in ("reference", "retrieval_identity", "source_discovery",
             "source_retrieval", "claim_location"):
    setattr(contradicted, name, None)
contradicted.claim_assessment = academic_claims.ClaimAssessmentResult(
    status="claim_contradicted", claim=source_claim.claim,
    evidence=[academic_claims.ClaimEvidence(
        text="The trial was inconclusive.", locator="s.pdf#page=2",
        source="s", page_number=2)],
    reasons=["Contrary evidence."])
release = orchestrator.assess_academic_release(
    checked.technical_claims, [contradicted],
    checked.discovered_claim_assessments, checked.claim_coverage)
check(release.status == "blocked_source_contradiction" and release.safe_to_present is False,
      "a source contradiction still withholds the answer, despite the "
      "methodological conflict that used to take precedence")
corrections = reconciliation.extract_academic_corrections(
    technical_claims=checked.technical_claims, source_claims=[contradicted],
    discovered_claim_assessments=checked.discovered_claim_assessments)
check(len(corrections.source) == 1 and not corrections.methodological
      and not corrections.contextual_methodological,
      "revision receives the source correction and no methodological one")

# ===========================================================================
print("\n[4] the non-blocking states keep their meaning")
not_established = copy.deepcopy(checked.discovered_claim_assessments)
for a in not_established:
    if a.contextual_methodological_consistency is not None:
        a.contextual_methodological_consistency.status = (
            academic_methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED)
release = orchestrator.assess_academic_release(
    [t for t in checked.technical_claims
     if t.methodological_consistency is None
     or t.methodological_consistency.status != academic_methodology.METHODOLOGICAL_STATUS_CONFLICT],
    [], not_established, checked.claim_coverage)
check(release.safe_to_present is True
      and release.status != orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
      "'not established' remains non-blocking and is not reported as a conflict")

unavailable = coverage.ClaimCoverageAssessment.unavailable("Synthetic failure.")
release = orchestrator.assess_academic_release(
    checked.technical_claims, [], checked.discovered_claim_assessments, unavailable)
check(release.status == "checking_incomplete",
      "incomplete coverage keeps its own status alongside a methodological conflict")
check(reconciliation.extract_academic_corrections(
          technical_claims=checked.technical_claims, source_claims=[],
          discovered_claim_assessments=checked.discovered_claim_assessments).is_empty(),
      "and with nothing correctable, no revision follows from it")
incomplete_final = copy.copy(checked)
incomplete_final.release = release
d = cf.assess_check_further(incomplete_final,
                            orchestrator.methodological_notes_index()).to_dict()
check(d["state"] == "worth_checking" and d["secondary"] == cf.INCOMPLETE_WITH_CONCERN_SECONDARY,
      "the reader sees the concern, told the check was incomplete")
quiet = copy.copy(checked)
quiet.release = release
quiet.discovered_claim_assessments = not_established
quiet.technical_claims = [t for t in checked.technical_claims
                          if t.methodological_consistency is None
                          or t.methodological_consistency.status
                          != academic_methodology.METHODOLOGICAL_STATUS_CONFLICT]
d = cf.assess_check_further(quiet, orchestrator.methodological_notes_index()).to_dict()
check(d["state"] == "incomplete" and d["worth_checking"] == [],
      "incomplete checking without a conflict is not presented as a concern")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
