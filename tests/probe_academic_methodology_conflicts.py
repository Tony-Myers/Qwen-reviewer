#!/usr/bin/env python3
"""Real-model diagnostic probe for methodological conflict boundaries.

This is deliberately a probe, not a regression test. It exercises the
production methodological prompt, schema, sampler, structured-output adapter,
and currently served llama-server model.

Model disagreements are reported, not asserted.
"""

import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_chat
import academic_claim_assessor
import academic_methodology as am
import llm_backend
import reviewer_notes


BASE_URL = "http://127.0.0.1:8081"
REPETITIONS = 3

C = am.METHODOLOGICAL_STATUS_CONSISTENT
X = am.METHODOLOGICAL_STATUS_CONFLICT
N = am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED


def served_model_path():
    with urllib.request.urlopen(
        f"{BASE_URL}/v1/models",
        timeout=5,
    ) as response:
        payload = json.loads(response.read().decode("utf-8"))

    models = payload.get("models") or payload.get("data") or []
    if not models:
        raise RuntimeError("llama-server returned no served model.")

    first = models[0]
    return first.get("model") or first.get("id") or first.get("name")


MODEL_PATH = served_model_path()
model = llm_backend.LlamaServerModel(
    model_path=MODEL_PATH,
    base_url=BASE_URL,
)


def assessor(*, prompt, schema):
    return academic_claim_assessor.generate_claim_assessor_output(
        model,
        None,
        prompt,
        schema,
    )


def claim(statement):
    return academic_chat.TechnicalClaim(
        type="diagnostic_probe",
        concept="diagnostic_probe",
        statement=statement,
        parameterisation=None,
    )


def passage(text):
    return reviewer_notes.Passage(
        note="DIAGNOSTIC METADATA MUST NOT REACH MODEL",
        heading="DIAGNOSTIC HEADING MUST NOT REACH MODEL",
        text=text,
        score=0.999,
    )


CASES = [
    {
        "id": "01_direct_consistency",
        "expected": C,
        "claim": (
            "Adjusting for baseline variables that strongly predict the "
            "outcome can improve statistical precision."
        ),
        "guidance": (
            "Adjustment for baseline variables that strongly predict the "
            "outcome can improve statistical precision by reducing residual "
            "variation."
        ),
        "boundary": "direct support",
    },
    {
        "id": "02_direct_conflict",
        "expected": X,
        "claim": (
            "A statistically significant baseline imbalance demonstrates "
            "that randomisation failed."
        ),
        "guidance": (
            "Chance baseline imbalances can occur despite valid randomisation. "
            "A statistically significant baseline imbalance does not by "
            "itself demonstrate that randomisation failed."
        ),
        "boundary": "explicit incompatible proposition",
    },
    {
        "id": "03_irrelevant_guidance",
        "expected": N,
        "claim": (
            "Adjusting for baseline variables that strongly predict the "
            "outcome can improve statistical precision."
        ),
        "guidance": (
            "Divergent transitions can indicate problematic Hamiltonian "
            "Monte Carlo geometry."
        ),
        "boundary": "irrelevant retrieved passage",
    },
    {
        "id": "04_stronger_than_guidance",
        "expected": N,
        "claim": (
            "Adjusting for a prognostic baseline variable always improves "
            "statistical precision."
        ),
        "guidance": (
            "Adjusting for a prognostic baseline variable can improve "
            "statistical precision."
        ),
        "boundary": "unsupported strengthening is not conflict",
    },
    {
        "id": "05_typically_vs_caution",
        "expected": N,
        "claim": (
            "For skewed posterior distributions, the HDI is typically "
            "narrower than the ETI."
        ),
        "guidance": (
            "An HDI should not be assumed to be narrower than an ETI merely "
            "because the posterior is skewed."
        ),
        "boundary": "caution does not necessarily contradict typically",
    },
    {
        "id": "06_always_vs_explicit_not_always",
        "expected": X,
        "claim": (
            "For skewed posterior distributions, the HDI is always narrower "
            "than the ETI."
        ),
        "guidance": (
            "For skewed posterior distributions, an HDI is not always "
            "narrower than an ETI."
        ),
        "boundary": "universal claim explicitly denied",
    },
    {
        "id": "07_sometimes_vs_not_always",
        "expected": N,
        "claim": (
            "For skewed posterior distributions, an HDI can sometimes be "
            "narrower than an ETI."
        ),
        "guidance": (
            "For skewed posterior distributions, an HDI is not always "
            "narrower than an ETI."
        ),
        "boundary": "not always does not contradict sometimes",
    },
    {
        "id": "08_omitted_condition",
        "expected": N,
        "claim": (
            "Covariate adjustment improves statistical precision."
        ),
        "guidance": (
            "Covariate adjustment can improve statistical precision when "
            "baseline covariates are strongly prognostic of the outcome."
        ),
        "boundary": "conditional support does not establish general claim",
    },
    {
        "id": "09_condition_absent_conflict",
        "expected": X,
        "claim": (
            "Covariate adjustment improves statistical precision regardless "
            "of whether the covariate predicts the outcome."
        ),
        "guidance": (
            "When a baseline covariate does not predict the outcome, adjusting "
            "for it does not provide the precision gain obtained from "
            "adjustment for a prognostic covariate."
        ),
        "boundary": "guidance explicitly defeats claim outside condition",
    },
    {
        "id": "10_same_topic_different_proposition",
        "expected": N,
        "claim": (
            "A 95% equal-tailed interval leaves equal posterior probability "
            "in each tail."
        ),
        "guidance": (
            "A highest-density interval contains the specified posterior "
            "probability while favouring values with higher posterior density."
        ),
        "boundary": "same broad topic but different proposition",
    },
    {
        "id": "11_weaker_claim_supported",
        "expected": C,
        "claim": (
            "A highest-density interval can differ from an equal-tailed "
            "interval for a skewed posterior distribution."
        ),
        "guidance": (
            "For a skewed posterior distribution, highest-density and "
            "equal-tailed intervals can have different endpoints."
        ),
        "boundary": "compatible material proposition",
    },
    {
        "id": "12_possible_vs_impossible",
        "expected": X,
        "claim": (
            "A valid randomisation procedure can produce chance baseline "
            "imbalances between groups."
        ),
        "guidance": (
            "Under a valid randomisation procedure, chance baseline "
            "imbalances between groups cannot occur."
        ),
        "boundary": "possibility explicitly denied",
    },
]


print("=" * 78)
print("ACADEMIC METHODOLOGY CONFLICT PROBE")
print("=" * 78)
print(f"Model: {MODEL_PATH}")
print(f"Cases: {len(CASES)}")
print(f"Repetitions: {REPETITIONS}")
print()

all_results = []
case_summaries = []

for case in CASES:
    print("-" * 78)
    print(case["id"])
    print(f"Boundary: {case['boundary']}")
    print(f"Expected: {case['expected']}")
    print(f"Claim: {case['claim']}")
    print(f"Guidance: {case['guidance']}")

    statuses = []

    for repetition in range(1, REPETITIONS + 1):
        try:
            result = am.assess_methodological_consistency(
                claim(case["claim"]),
                [passage(case["guidance"])],
                assessor,
            )
            status = result.status
            reason = result.reasons[0]
        except Exception as exc:
            status = "ERROR"
            reason = f"{type(exc).__name__}: {exc}"

        statuses.append(status)

        match = status == case["expected"]
        false_conflict = (
            status == X
            and case["expected"] != X
        )

        all_results.append(
            {
                "case": case["id"],
                "repetition": repetition,
                "expected": case["expected"],
                "observed": status,
                "match": match,
                "false_conflict": false_conflict,
                "reason": reason,
            }
        )

        flag = "MATCH" if match else "DISAGREE"
        if false_conflict:
            flag += " *** FALSE CONFLICT ***"

        print(
            f"  run {repetition}: {status} [{flag}]"
        )
        print(f"    reason: {reason}")

    counts = Counter(statuses)
    unanimous = len(counts) == 1
    false_conflicts = sum(
        1 for status in statuses
        if status == X and case["expected"] != X
    )

    case_summaries.append(
        {
            "case": case["id"],
            "expected": case["expected"],
            "statuses": statuses,
            "unanimous": unanimous,
            "false_conflicts": false_conflicts,
        }
    )

    print(f"  distribution: {dict(counts)}")
    print(f"  unanimous: {unanimous}")
    print()


print("=" * 78)
print("SUMMARY")
print("=" * 78)

matches = sum(result["match"] for result in all_results)
false_conflicts = sum(
    result["false_conflict"] for result in all_results
)
errors = sum(
    result["observed"] == "ERROR"
    for result in all_results
)
unanimous_cases = sum(
    summary["unanimous"]
    for summary in case_summaries
)

print(f"Total assessments: {len(all_results)}")
print(f"Expected-status matches: {matches}/{len(all_results)}")
print(f"False conflicts: {false_conflicts}")
print(f"Errors: {errors}")
print(
    f"Cases unanimous across repetitions: "
    f"{unanimous_cases}/{len(case_summaries)}"
)

print("\nPer-case:")
for summary in case_summaries:
    print(
        f"  {summary['case']}: "
        f"expected={summary['expected']} "
        f"observed={summary['statuses']} "
        f"false_conflicts={summary['false_conflicts']}"
    )

print("\nNOTE: This is a diagnostic probe. Disagreements do not fail the process.")
