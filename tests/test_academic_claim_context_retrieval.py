#!/usr/bin/env python3
"""
A split-out claim's guidance is retrieved with its verified answer context.

    python3 tests/test_academic_claim_context_retrieval.py

Reproduces the live case of 1 October 2026 ("What is Rubin's relative
efficiency formula for multiple imputation, and what does it imply about
the number of imputations?"). Claims split out of the answer lost the
words naming their topic -- "Increasing m does not recover unobserved
information" says nothing about imputation -- so their claim-only search
returned MCMC, regression and repeated-measures sections, and the
relative-efficiency section that states them was never judged against.

A claim with a verified location in the answer now searches with its
application-owned source sentence and bounded context, through the same
query used for contextual assessment. Run here through the real
claim-coverage pipeline, answer-location resolution, retrieval over the
real reviewer notes, orchestrator and evidence layer. Only the model
calls are replaced, and the judge returns "not established" throughout,
so nothing depends on stochastic output. Checked:

  1. split-out claims use the production contextual query built from the
     resolved answer location; claims without one keep the claim-only query;
  2. the relative-efficiency section now reaches 13 of the 15 split-out
     claims instead of 11, with none of the 11 lost;
  3. the original question never enters a claim search;
  4. each judge prompt contains only guidance retrieved for that claim,
     and asks about the claim alone, not the answer sentence;
  5. an unrelated HMC claim placed straight after the Missing Data text
     is still judged without Missing Data guidance and is not routed to
     Missing Data further reading.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_chat                          # noqa: E402
import academic_check_further as cf           # noqa: E402
import academic_claim_coverage as coverage    # noqa: E402
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
            "imputations")
MISSING_DATA = "Missing Data, Dropout and Analysis Populations"
RE_SECTION = (MISSING_DATA, "How does FMI affect relative efficiency?")

# The answer as Academic Chat produced it.
ANSWER = (
    "Rubin's relative efficiency (RE) formula for multiple imputation "
    "approximates the efficiency of using a finite number of imputations m "
    "compared to an infinite number. The standard approximation is "
    "RE ≈ 1 / (1 + FMI/m), where FMI is the fraction of missing information. "
    "This formula implies that for a fixed m, relative efficiency decreases "
    "as FMI increases. Conversely, increasing m improves efficiency, "
    "bringing the estimate closer to the result obtained with infinitely "
    "many imputations.\n\n"
    "Practically, this relationship suggests that high FMI requires more "
    "imputations to achieve the same efficiency as low FMI. However, "
    "relative efficiency is often high even with small m. For instance, if "
    "FMI = 0.3, m = 5 yields RE ≈ 0.94. To achieve RE ≥ 0.95, the rule of "
    "thumb m ≥ 19 × FMI applies (approximately 6 imputations for "
    "FMI = 0.3). Achieving RE ≈ 0.99 requires m ≈ 100 × FMI.\n\n"
    "It is important to distinguish this finite-imputation efficiency from "
    "the loss of information due to missing data itself. Increasing m "
    "reduces Monte Carlo uncertainty from the imputation process but does "
    "not recover unobserved information. Consequently, while point "
    "estimates may be stable with few imputations, larger m is often "
    "recommended to ensure the stability and replicability of standard "
    "errors, confidence intervals, and p-values, which are more sensitive "
    "to Monte Carlo error than point estimates."
)

# The fifteen claims discovered in the live run, with verbatim anchors.
DISCOVERED = [
    ("The standard approximation for Rubin's relative efficiency (RE) is "
     "RE ≈ 1 / (1 + FMI/m).",
     "The standard approximation is RE ≈ 1 / (1 + FMI/m)"),
    ("For a fixed number of imputations m, relative efficiency decreases as "
     "the fraction of missing information (FMI) increases.",
     "for a fixed m, relative efficiency decreases as FMI increases"),
    ("Increasing the number of imputations m improves efficiency, bringing "
     "the estimate closer to the result obtained with infinitely many "
     "imputations.",
     "increasing m improves efficiency, bringing the estimate closer to the "
     "result obtained with infinitely many imputations"),
    ("High FMI requires more imputations to achieve the same efficiency as "
     "low FMI.",
     "high FMI requires more imputations to achieve the same efficiency as "
     "low FMI"),
    ("Relative efficiency is often high even with small m.",
     "relative efficiency is often high even with small m"),
    ("If FMI = 0.3 and m = 5, the relative efficiency is approximately 0.94.",
     "if FMI = 0.3, m = 5 yields RE ≈ 0.94"),
    ("To achieve RE ≥ 0.95, the rule of thumb is m ≥ 19 × FMI.",
     "To achieve RE ≥ 0.95, the rule of thumb m ≥ 19 × FMI applies"),
    ("For FMI = 0.3, the rule of thumb m ≥ 19 × FMI results in approximately "
     "6 imputations.",
     "approximately 6 imputations for FMI = 0.3"),
    ("Achieving RE ≈ 0.99 requires m ≈ 100 × FMI.",
     "Achieving RE ≈ 0.99 requires m ≈ 100 × FMI"),
    ("Increasing m reduces Monte Carlo uncertainty from the imputation "
     "process.",
     "Increasing m reduces Monte Carlo uncertainty from the imputation "
     "process"),
    ("Increasing m does not recover unobserved information.",
     "does not recover unobserved information"),
    ("Standard errors, confidence intervals, and p-values are more sensitive "
     "to Monte Carlo error than point estimates.",
     "which are more sensitive to Monte Carlo error than point estimates"),
    ("Larger m is often recommended to ensure the stability and "
     "replicability of standard errors, confidence intervals, and p-values.",
     "larger m is often recommended to ensure the stability and "
     "replicability of standard errors, confidence intervals, and p-values"),
    ("Rubin's relative efficiency (RE) formula for multiple imputation "
     "approximates the efficiency of using a finite number of imputations m "
     "compared to an infinite number.",
     "Rubin's relative efficiency (RE) formula for multiple imputation "
     "approximates the efficiency of using a finite number of imputations m "
     "compared to an infinite number"),
    ("Point estimates may be stable with few imputations.",
     "point estimates may be stable with few imputations"),
]

# The claims the draft itself structured, which have no answer location.
DRAFT_CLAIMS = [
    academic_chat.TechnicalClaim(
        type="formula", concept="Relative Efficiency of Multiple Imputation",
        statement="RE ≈ 1 / (1 + FMI/m)", parameterisation=None),
    academic_chat.TechnicalClaim(
        type="rule", concept="Imputation Count for RE >= 0.95",
        statement="m >= 19 * FMI", parameterisation=None),
]

HMC_SENTENCE = ("Divergent transitions in Hamiltonian Monte Carlo indicate "
                "problematic posterior geometry.")
HMC_CLAIM = HMC_SENTENCE


def run(answer, discovered):
    def coverage_model(*, prompt, schema):
        if (schema == coverage.claim_discovery_output_schema()
                and "ANSWER DRAFT" in prompt):
            return {"discovered_claims": [
                {"type": "interpretation", "concept": "discovered",
                 "statement": statement, "parameterisation": None,
                 "source_anchor": anchor}
                for statement, anchor in discovered]}
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
        return {"material_restriction_omitted": False}

    searches = []

    def claim_retriever(query):
        guidance = orchestrator.retrieve_methodological_context(query)
        searches.append((query, guidance.passages))
        return guidance

    prompts = []

    def judge(*, prompt, schema):
        prompts.append(prompt)
        return {"status": am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
                "reason": "Synthetic deterministic judgement."}

    question_guidance = orchestrator.retrieve_methodological_context(QUESTION)
    result = orchestrator.assess_academic_draft(
        academic_chat.AcademicDraft(answer_draft=answer, references=[],
                                    source_claims=[],
                                    technical_claims=list(DRAFT_CLAIMS)),
        local_guidance=question_guidance,
        technical_verifier=academic_technical.verify_technical_claim,
        methodological_assessor=judge,
        claim_methodological_retriever=claim_retriever,
        coverage_assessor=coverage_assessor,
        material_restriction_assessor=restriction_assessor,
    )
    return result, question_guidance, searches, prompts


def sections(passages):
    return [(p.note, p.heading) for p in passages]


result, question_guidance, searches, prompts = run(ANSWER, DISCOVERED)
contexts = {a.discovered_claim.claim.statement: a.source_context
            for a in result.discovered_claim_assessments}
judged = {t.claim.statement: t.methodological_consistency
          for t in result.technical_claims}

# ===========================================================================
print("\n[1] the production answer-location path supplies the query")
check(len(contexts) == len(DISCOVERED),
      f"every discovered claim was located in the answer ({len(contexts)})")
expected_queries = [
    orchestrator._contextual_claim_methodological_query(
        academic_chat.TechnicalClaim(type="interpretation",
                                     concept="discovered",
                                     statement=s, parameterisation=None),
        contexts[s])
    for s, _ in DISCOVERED]
queries = [q for q, _ in searches]
check(all(q in queries for q in expected_queries),
      "each split-out claim searches with its resolved sentence and context")
check(all(orchestrator._technical_claim_methodological_query(c) in queries
          for c in DRAFT_CLAIMS),
      "claims without an answer location keep the claim-only query")
check(len(searches) == len(DISCOVERED) + len(DRAFT_CLAIMS),
      f"one standalone search per claim ({len(searches)})")

# ===========================================================================
print("\n[2] the relative-efficiency section reaches more split-out claims")
before, after = {}, {}
for statement, _ in DISCOVERED:
    claim = academic_chat.TechnicalClaim(type="interpretation",
                                         concept="discovered",
                                         statement=statement,
                                         parameterisation=None)
    before[statement] = RE_SECTION in sections(
        orchestrator.retrieve_methodological_context(
            orchestrator._technical_claim_methodological_query(claim)).passages)
    after[statement] = RE_SECTION in sections(judged[statement].passages)
n_before, n_after = sum(before.values()), sum(after.values())
check(n_before == 11, f"claim-only search: {n_before} of 15 (the live behaviour)")
check(n_after >= 13, f"with the verified context: {n_after} of 15")
lost = [s for s in before if before[s] and not after[s]]
check(not lost, "no claim that reached the section before loses it"
      + (f": {lost}" if lost else ""))

# ===========================================================================
print("\n[3] the original question never enters a claim search")
check(all(QUESTION not in q and "Rubin's relative efficiency formula for "
          "multiple imputation, and what" not in q for q in queries),
      "no claim search contains the question")

# ===========================================================================
print("\n[4] each judge sees only its own guidance, about its own claim")
question_only = [p for p in question_guidance.passages]
own_ok = alien_ok = claim_only_ok = True
for statement, consistency in judged.items():
    prompt = next(p for p in prompts if statement in p)
    own = {(p.note, p.heading, p.text) for p in consistency.passages}
    if not all(p.text[:200] in prompt for p in consistency.passages):
        own_ok = False
    for p in question_only:
        if (p.note, p.heading, p.text) not in own and p.text[:200] in prompt:
            alien_ok = False
    if "VERIFIED SOURCE SENTENCE" in prompt or "BOUNDED ANSWER CONTEXT" in prompt:
        claim_only_ok = False
check(own_ok, "every prompt contains the guidance retrieved for its claim")
check(alien_ok, "no prompt contains question guidance its claim did not retrieve")
check(claim_only_ok, "standalone prompts judge the claim alone, without the "
      "answer sentence or context")

# ===========================================================================
print("\n[5] an unrelated HMC claim right after the Missing Data text")
hmc_answer = ANSWER + " " + HMC_SENTENCE
hmc_result, _, hmc_searches, _ = run(
    hmc_answer, DISCOVERED + [(HMC_CLAIM, HMC_SENTENCE[:-1])])
hmc_context = next(a.source_context for a in hmc_result.discovered_claim_assessments
                   if a.discovered_claim.claim.statement == HMC_CLAIM)
check("Monte Carlo error than point estimates" in hmc_context.context_excerpt,
      "its bounded context includes the preceding Missing Data sentence")
hmc = next(t.methodological_consistency for t in hmc_result.technical_claims
           if t.claim.statement == HMC_CLAIM)
check(all(p.note != MISSING_DATA for p in hmc.passages),
      "it is judged without Missing Data guidance: "
      + "; ".join(f"{n} - {h}" for n, h in sections(hmc.passages)))
evidence = cf.assess_check_further(
    hmc_result, orchestrator.methodological_notes_index()).to_dict()
routed = {r["statement"]: r["routed_to"]
          for r in evidence["diagnostics"]["routing"]}
check(routed.get(HMC_CLAIM) is None,
      f"it is not routed to Missing Data further reading ({routed.get(HMC_CLAIM)})")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
