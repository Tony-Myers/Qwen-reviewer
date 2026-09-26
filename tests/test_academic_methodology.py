#!/usr/bin/env python3
"""Regression tests for Academic Chat methodological consistency."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_chat
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

schema = am.methodological_consistency_output_schema()

assert set(schema["properties"]["status"]["enum"]) == set(
    am.METHODOLOGICAL_STATUSES
)
assert schema["additionalProperties"] is False

print("PASS: schema exposes only methodological-consistency statuses")


print("\n[2] prompt preserves methodological boundary")

hdi_claim = claim(
    "For skewed posterior distributions, the HDI is typically narrower "
    "than the ETI."
)

prompt = am.build_methodological_consistency_prompt(
    hdi_claim,
    passages,
)

assert hdi_claim.statement in prompt
assert "should not be assumed to be narrower" in prompt
assert "Do not use outside knowledge." in prompt
assert (
    "Absence of a warning or contrary statement is not evidence of consistency."
    in prompt
)

print("PASS: prompt contains claim and guidance")
print("PASS: prompt forbids outside knowledge")
print("PASS: silence is not treated as consistency")


print("\n[2b] prompt preserves quantifiers and modality")

normalised_prompt = " ".join(prompt.split())

assert (
    "not necessarily, universally, or automatically true"
    in normalised_prompt
)
assert (
    "may, sometimes, often, or under some conditions be true"
    in normalised_prompt
)
assert (
    "frequency, modality, and quantifiers as material"
    in normalised_prompt
)

print("PASS: prompt prevents caution from becoming contradiction")
print("PASS: prompt treats frequency, modality, and quantifiers as material")


print("\n[2c] prompt distinguishes non-establishment from contradiction")

assert (
    "A stronger claim is not established merely because the guidance supports "
    "a weaker version" in normalised_prompt
)
assert (
    "unsupported strengthening is not by itself a methodological conflict"
    in normalised_prompt
)
assert (
    "methodological_conflict requires the guidance to establish an "
    "incompatible proposition" in normalised_prompt
)
assert (
    "Omitting a condition from a claim does not by itself establish conflict"
    in normalised_prompt
)

print("PASS: unsupported strengthening maps to non-establishment")
print("PASS: conflict requires an incompatible proposition")
print("PASS: omitted conditions are not automatically contradictions")


print("\n[3] structurally valid conflict is representable")

result = am.build_methodological_consistency(
    hdi_claim,
    passages,
    {
        "status": "methodological_conflict",
        "reason": (
            "The guidance explicitly warns against assuming that skewness "
            "makes an HDI narrower than an ETI."
        ),
    },
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
    {
        "status": "methodologically_consistent",
        "reason": (
            "The guidance directly describes an ETI as leaving equal "
            "posterior probability in each tail."
        ),
    },
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
    {
        "status": "methodological_consistency_not_established",
        "reason": (
            "The guidance concerns HMC divergences rather than ETI and HDI "
            "interval width."
        ),
    },
)

assert (
    not_established.status
    == am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED
)

print("PASS: irrelevant guidance remains not established")


print("\n[6] injected assessor receives bounded prompt and schema")

captured = {}


def fake_assessor(*, prompt, schema):
    captured["prompt"] = prompt
    captured["schema"] = schema
    return {
        "status": "methodological_conflict",
        "reason": "The supplied guidance directly conflicts with the claim.",
    }


assessed = am.assess_methodological_consistency(
    hdi_claim,
    passages,
    fake_assessor,
)

assert assessed.status == am.METHODOLOGICAL_STATUS_CONFLICT
assert captured["schema"] == am.methodological_consistency_output_schema()

print("PASS: injected assessor output becomes application-owned result")


print("\n[7] malformed assessor output is rejected")

bad_outputs = [
    None,
    [],
    {},
    {"status": "methodological_conflict", "reason": ""},
    {"status": "verified", "reason": "Unsupported status."},
    {
        "status": "methodological_conflict",
        "reason": "Conflict.",
        "extra": True,
    },
    {
        "status": "methodological_conflict",
        "reason": " ".join(["word"] * 31),
    },
    {
        "status": "methodological_conflict",
        "reason": "Conflict.",
        "note": "Model-supplied provenance must not be accepted.",
    },
]

for output in bad_outputs:
    try:
        am.build_methodological_consistency(
            hdi_claim,
            passages,
            output,
        )
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError(
            f"Malformed assessor output was accepted: {output!r}"
        )

print("PASS: malformed assessor outputs are rejected")

print("\nAll methodological-consistency checks passed.")
