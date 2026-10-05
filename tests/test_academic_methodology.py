#!/usr/bin/env python3
"""Regression tests for Academic Chat methodological consistency."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_chat
from methodology_fixtures import methodology_output, methodology_outputs
import academic_methodology as am
import reviewer_notes


def claim(statement):
    return academic_chat.TechnicalClaim(
        type="comparison",
        concept="ETI and HDI comparison",
        statement=statement,
        parameterisation=None,
    )


GUIDANCE = """
An equal-tailed interval (ETI) leaves equal posterior probability in each tail.

A highest-density interval (HDI) contains the specified posterior probability
while favouring values with higher posterior density.

An HDI should not be assumed to be narrower than an ETI merely because the
posterior is skewed. Neither construction is automatically more precise, more
credible, or generally preferable merely because its interval is narrower.
""".strip()

passages = [
    reviewer_notes.Passage(
        note="Bayesian Decision Rules and Posterior Interpretation",
        heading="Are all 95% credible intervals the same?",
        text=GUIDANCE,
        score=0.56,
    )
]


print("[1] schema is bounded")

schemas = [am.methodological_coexistence_output_schema(),
           am.methodological_establishment_output_schema()]
for schema, field in zip(schemas, ("can_both_be_true", "guidance_establishes_claim")):
    assert set(schema["properties"]) == {"claim_proposition", "guidance_proposition", field, "reason"}
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"][field]["enum"] == ["yes", "no", "unclear"]
    assert schema["additionalProperties"] is False
print("PASS: two strict bounded schemas, no model-owned application status")


print("\n[2] prompt preserves methodological boundary")

hdi_claim = claim(
    "For skewed posterior distributions, the HDI is typically narrower "
    "than the ETI."
)

prompt = am.build_methodological_coexistence_prompt(
    hdi_claim,
    passages,
)

assert hdi_claim.statement in prompt
assert "should not be assumed to be narrower" in prompt
assert "Do not use outside knowledge." in prompt
assert (
    "Do not decide whether the guidance supports the claim."
    in prompt
)

print("PASS: prompt contains claim and guidance")
print("PASS: prompt forbids outside knowledge")
print("PASS: silence is not treated as consistency")


print("\n[2b/c] independent rules preserve quantifiers and proposition strength")
normalised_prompt = " ".join(prompt.split())
establishment_prompt = am.build_methodological_establishment_prompt(hdi_claim, passages)
establishment_rules = " ".join(establishment_prompt.split())
assert '"Typically X" and "not always/universally X" can both be true.' in normalised_prompt
assert "frequency, quantifiers, modality, direction, degree, conditions and context" in normalised_prompt
assert "A weaker proposition does not contradict a stronger proposition merely because the stronger proposition is not established." in normalised_prompt
assert "A warning that an inference is not established does not by itself establish the contrary substantive proposition." in normalised_prompt
assert "Do not decide whether the guidance supports the claim." in prompt
assert "A weaker proposition does not establish a stronger proposition." in establishment_prompt
assert "Compatibility alone is not support." in establishment_prompt
assert "Do not decide whether the propositions conflict." in establishment_prompt
assert "complete claim, including its important quantifiers, modality, frequency, direction, degree, conditions and context" in establishment_rules
print("PASS: coexistence and establishment are bounded independently")


print("\n[2d] methodology prompt ignores non-semantic claim metadata")

metadata_variant_claim = academic_chat.TechnicalClaim(
    type="different_generated_type",
    concept="different_generated_concept",
    statement=hdi_claim.statement,
    parameterisation=hdi_claim.parameterisation,
)

metadata_variant_prompt = am.build_methodological_coexistence_prompt(
    metadata_variant_claim,
    passages,
)

assert metadata_variant_prompt == prompt

print("PASS: type and concept do not alter methodology assessment prompt")


print("\n[2e] methodology prompt excludes guidance retrieval metadata")

assert passages[0].text in prompt
assert passages[0].note not in prompt
assert passages[0].heading not in prompt
assert f"score: {passages[0].score}" not in prompt

print("PASS: methodological assessment receives guidance text")
print("PASS: note, heading, and retrieval score remain outside semantic assessment")


print("\n[3] structurally valid conflict is representable")

result = am.build_methodological_consistency(
    hdi_claim,
    passages,
    *methodology_outputs('methodological_conflict', "The guidance explicitly warns against assuming that skewness "
            "makes an HDI narrower than an ETI."),
)

assert result.status == am.METHODOLOGICAL_STATUS_CONFLICT
assert result.claim.statement == hdi_claim.statement
assert result.passages[0].note == (
    "Bayesian Decision Rules and Posterior Interpretation"
)

payload = result.to_dict()
assert payload["passages"][0]["heading"] == (
    "Are all 95% credible intervals the same?"
)
assert "text" not in payload["passages"][0]

print("PASS: conflict retains claim and reviewer-note provenance")
print("PASS: normal serialisation omits full reviewer-note text")


print("\n[4] compatibility remains distinct from conflict")

consistent = am.build_methodological_consistency(
    claim(
        "A 95% ETI leaves equal posterior probability in each tail."
    ),
    passages,
    *methodology_outputs('methodologically_consistent', "The guidance directly describes an ETI as leaving equal "
            "posterior probability in each tail."),
)

assert consistent.status == am.METHODOLOGICAL_STATUS_CONSISTENT

print("PASS: directly compatible proposition can be marked consistent")


print("\n[5] irrelevant guidance does not become consistency")

unrelated = [
    reviewer_notes.Passage(
        note="Bayesian Computation",
        heading="Divergent transitions",
        text=(
            "Divergent transitions can indicate problematic Hamiltonian "
            "Monte Carlo geometry."
        ),
        score=0.31,
    )
]

not_established = am.build_methodological_consistency(
    hdi_claim,
    unrelated,
    *methodology_outputs('methodological_consistency_not_established', "The guidance concerns HMC divergences rather than ETI and HDI "
            "interval width."),
)

assert (
    not_established.status
    == am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED
)

print("PASS: irrelevant guidance remains not established")


print("\n[6] injected assessor receives bounded prompt and schema")

captured = []


def fake_assessor(*, prompt, schema):
    captured.append((prompt, schema))
    return methodology_output(schema, 'methodological_conflict', "The supplied guidance directly conflicts with the claim.")


assessed = am.assess_methodological_consistency(
    hdi_claim,
    passages,
    fake_assessor,
)

assert assessed.status == am.METHODOLOGICAL_STATUS_CONFLICT
assert [schema for _, schema in captured] == schemas
assert len(assessed.reasons) == 2

print("PASS: injected assessor output becomes application-owned result")


print("\n[7] malformed assessor output is rejected")

valid_pair = methodology_outputs(am.METHODOLOGICAL_STATUS_CONSISTENT)
for stage, field in enumerate(("can_both_be_true", "guidance_establishes_claim")):
    valid = valid_pair[stage]
    bad_outputs = [None, [], {}, dict(valid, reason=""), dict(valid, **{field: "verified"}),
                   dict(valid, extra=True), dict(valid, reason=" ".join(["word"] * 31)),
                   dict(valid, note="Model-supplied provenance must not be accepted.")]
    for key in valid:
        missing = dict(valid)
        del missing[key]
        bad_outputs.append(missing)
    for output in bad_outputs:
        pair = list(valid_pair)
        pair[stage] = output
        try:
            am.build_methodological_consistency(hdi_claim, passages, *pair)
        except am.MethodologicalAssessmentOutputError:
            pass
        else:
            raise AssertionError(f"Malformed stage {stage} output accepted: {output!r}")

print("PASS: malformed assessor outputs raise the dedicated output error")


print("\n[7b] application-owned input failures remain distinct")

try:
    am.build_methodological_consistency(
        hdi_claim,
        [],
        *methodology_outputs('methodologically_consistent', "Synthetic valid assessor judgement."),
    )
except am.MethodologicalAssessmentOutputError:
    raise AssertionError(
        "Invalid application-owned passages were misclassified as model output."
    )
except ValueError:
    pass
else:
    raise AssertionError("Invalid application-owned passages were accepted.")

print("PASS: application-owned validation is not reclassified as model output")


print("\n[8] contextual methodology keeps answer context distinct from guidance")

import academic_claim_coverage

rct_claim = academic_chat.TechnicalClaim(
    type="statistical principle",
    concept="covariate adjustment",
    statement=(
        "Adjusting for baseline variables that strongly predict the outcome "
        "reduces residual variation."
    ),
    parameterisation=None,
)

rct_context = academic_claim_coverage.ClaimSourceContext(
    source_sentence=(
        "Adjusting for baseline variables that strongly predict the outcome "
        "reduces residual variation."
    ),
    source_sentence_start=112,
    source_sentence_end=224,
    context_excerpt=(
        "In randomised trials, the primary rationale for covariate adjustment "
        "is statistical efficiency, not confounding control. Adjusting for "
        "baseline variables that strongly predict the outcome reduces residual "
        "variation."
    ),
    context_start=0,
    context_end=224,
)

rct_passages = [
    reviewer_notes.Passage(
        note="Baseline Balance and Covariate Adjustment in Randomised Trials",
        heading="Why adjust for baseline covariates in a randomised trial?",
        text=(
            "An important reason for covariate adjustment in a randomised "
            "trial is improved statistical efficiency. Adjustment for "
            "baseline variables that strongly predict the outcome can reduce "
            "residual variation."
        ),
        score=0.45,
    )
]

contextual_prompt = am.build_contextual_methodological_coexistence_prompt(
    claim=rct_claim,
    source_context=rct_context,
    passages=rct_passages,
)

assert rct_claim.statement in contextual_prompt
assert rct_context.source_sentence in contextual_prompt
assert rct_context.context_excerpt in contextual_prompt
assert rct_passages[0].text in contextual_prompt

normalised_contextual_prompt = " ".join(contextual_prompt.split())

assert (
    "use the verified answer context only to interpret restrictions that govern "
    "this occurrence of the generated claim"
    in normalised_contextual_prompt.lower()
)
assert (
    "answer context is not methodological guidance"
    in normalised_contextual_prompt.lower()
)
assert (
    "only the supplied curated methodological guidance"
    in normalised_contextual_prompt.lower()
)
assert (
    "do not treat the answer context as changing the stored claim"
    in normalised_contextual_prompt.lower()
)

print("PASS: contextual prompt retains claim, verified context, and guidance")
print("PASS: answer context has interpretive but not methodological authority")


print("\n[8b] contextual prompt ignores non-semantic claim metadata")

rct_metadata_variant = academic_chat.TechnicalClaim(
    type="different_generated_type",
    concept="different_generated_concept",
    statement=rct_claim.statement,
    parameterisation=rct_claim.parameterisation,
)

contextual_metadata_variant_prompt = (
    am.build_contextual_methodological_coexistence_prompt(
        claim=rct_metadata_variant,
        source_context=rct_context,
        passages=rct_passages,
    )
)

assert contextual_metadata_variant_prompt == contextual_prompt

print("PASS: type and concept do not alter contextual methodology prompt")


print("\n[9] contextual methodology retains application-owned provenance")

contextual_result = am.build_contextual_methodological_consistency(
    claim=rct_claim,
    source_context=rct_context,
    passages=rct_passages,
    coexistence_output=methodology_outputs(am.METHODOLOGICAL_STATUS_CONSISTENT)[0],
    establishment_output=methodology_outputs(am.METHODOLOGICAL_STATUS_CONSISTENT)[1],
)

assert isinstance(
    contextual_result,
    am.ContextualMethodologicalConsistencyResult,
)
assert contextual_result.status == am.METHODOLOGICAL_STATUS_CONSISTENT
assert contextual_result.claim is rct_claim
assert contextual_result.source_context is rct_context
assert contextual_result.passages == rct_passages

print("PASS: contextual result remains distinct from standalone result")
print("PASS: claim, source context, and guidance provenance remain application-owned")


print("\n[10] contextual assessor receives only bounded judgement authority")

contextual_captured = []


def fake_contextual_assessor(*, prompt, schema):
    contextual_captured.append((prompt, schema))
    return methodology_output(schema, 'methodologically_consistent', "The context-qualified proposition matches the supplied guidance.")


contextual_assessed = am.assess_contextual_methodological_consistency(
    claim=rct_claim,
    source_context=rct_context,
    passages=rct_passages,
    assessor=fake_contextual_assessor,
)

assert contextual_assessed.status == am.METHODOLOGICAL_STATUS_CONSISTENT
assert [schema for _, schema in contextual_captured] == schemas
assert len(contextual_assessed.reasons) == 2
assert contextual_assessed.reasons == [
    "The context-qualified proposition matches the supplied guidance.",
    "The context-qualified proposition matches the supplied guidance.",
]
print("PASS: contextual assessment reuses both bounded schemas in order")
print("PASS: model cannot supply claim, context, or guidance provenance")



assert am.build_methodological_establishment_prompt(metadata_variant_claim, passages) == establishment_prompt
assert passages[0].text in establishment_prompt
assert passages[0].note not in establishment_prompt
assert passages[0].heading not in establishment_prompt
contextual_establishment = am.build_contextual_methodological_establishment_prompt(
    claim=rct_claim, source_context=rct_context, passages=rct_passages)
assert contextual_establishment == am.build_contextual_methodological_establishment_prompt(
    claim=rct_metadata_variant, source_context=rct_context, passages=rct_passages)
assert rct_context.source_sentence in contextual_establishment
assert rct_context.context_excerpt in contextual_establishment
assert "The answer context is not methodological guidance" in contextual_establishment
assert "Do not rewrite, repair, strengthen, or weaken the generated claim." in contextual_establishment

print("\nAll methodological-consistency checks passed.")
