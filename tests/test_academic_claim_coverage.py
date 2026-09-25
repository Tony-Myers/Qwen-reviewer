#!/usr/bin/env python3
"""Contract tests for Academic Chat technical-claim coverage."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import academic_chat
import academic_claim_coverage as coverage


def technical_claim(statement):
    return academic_chat.TechnicalClaim(
        type="comparison",
        concept="ETI and HDI comparison",
        statement=statement,
        parameterisation=None,
    )


ANSWER = """
A 95% ETI leaves 2.5% of posterior probability in each tail. A 95% HDI
contains high-density posterior values and need not have equal tail
probabilities.

For a skewed posterior, the HDI is not necessarily narrower than the ETI.
For many skewed distributions, however, the HDI will be narrower than the ETI.
A narrower interval is not automatically more precise or preferable.
""".strip()

EXISTING = [
    technical_claim(
        "A 95% ETI leaves 2.5% of posterior probability in each tail."
    ),
    technical_claim(
        "For a skewed posterior, the HDI is not necessarily narrower "
        "than the ETI."
    ),
    technical_claim(
        "A narrower interval is not automatically more precise or preferable."
    ),
]


print("[1] strict coverage schema exposes only missing claims")

schema = coverage.claim_coverage_output_schema()

assert set(schema) == {
    "type",
    "properties",
    "required",
    "additionalProperties",
}
assert schema["required"] == ["missing_claims"]
assert schema["additionalProperties"] is False

missing_schema = schema["properties"]["missing_claims"]
assert missing_schema["type"] == "array"

item = missing_schema["items"]
assert set(item["required"]) == {
    "type",
    "concept",
    "statement",
    "parameterisation",
}
assert item["additionalProperties"] is False

print("PASS: coverage schema is structurally bounded")


print("\n[2] coverage prompt has a narrow discovery role")

prompt = coverage.build_claim_coverage_prompt(
    answer_draft=ANSWER,
    existing_claims=EXISTING,
)

assert ANSWER in prompt

for claim in EXISTING:
    assert claim.statement in prompt

assert "USER QUESTION" not in prompt
assert "LOCAL METHODOLOGICAL GUIDANCE" not in prompt
assert "release_allowed" not in prompt
assert "methodologically_consistent" not in prompt

normalized = " ".join(prompt.lower().split())

assert "do not judge whether" in normalized
assert "true" in normalized
assert "false" in normalized
assert "not already represented" in normalized
assert "material" in normalized
assert "checkable" in normalized

print("PASS: coverage sees only answer and existing structured claims")
print("PASS: coverage discovers omissions rather than judging truth")


print("\n[3] genuinely missing claim becomes application-owned TechnicalClaim")

result = coverage.build_claim_coverage(
    answer_draft=ANSWER,
    existing_claims=EXISTING,
    assessor_output={
        "missing_claims": [
            {
                "type": "comparison",
                "concept": "HDI and ETI width in skewed posteriors",
                "statement": (
                    "For many skewed distributions, the HDI will be "
                    "narrower than the ETI."
                ),
                "parameterisation": None,
            }
        ]
    },
)

assert len(result.missing_claims) == 1
assert isinstance(
    result.missing_claims[0],
    academic_chat.TechnicalClaim,
)
assert result.missing_claims[0].statement == (
    "For many skewed distributions, the HDI will be narrower than the ETI."
)

print("PASS: missing proposition becomes an ordinary TechnicalClaim")


print("\n[4] complete coverage permits an empty missing-claim set")

complete = coverage.build_claim_coverage(
    answer_draft="A concise answer.",
    existing_claims=[],
    assessor_output={"missing_claims": []},
)

assert complete.missing_claims == []

print("PASS: assessor may report no missing technical claims")


print("\n[5] duplicate existing propositions are not accepted as missing")

duplicate_output = {
    "missing_claims": [
        {
            "type": EXISTING[1].type,
            "concept": EXISTING[1].concept,
            "statement": EXISTING[1].statement,
            "parameterisation": EXISTING[1].parameterisation,
        }
    ]
}

duplicate_result = coverage.build_claim_coverage(
    answer_draft=ANSWER,
    existing_claims=EXISTING,
    assessor_output=duplicate_output,
)

assert duplicate_result.missing_claims == []

print("PASS: exact existing claims are application-deduplicated")


print("\n[6] assessor cannot supply verification or provenance")

bad_outputs = [
    None,
    [],
    {},
    {"missing_claims": [], "status": "coverage_complete"},
    {
        "missing_claims": [
            {
                "type": "comparison",
                "concept": "example",
                "statement": "Synthetic proposition.",
                "parameterisation": None,
                "verified": True,
            }
        ]
    },
    {
        "missing_claims": [
            {
                "type": "",
                "concept": "example",
                "statement": "Synthetic proposition.",
                "parameterisation": None,
            }
        ]
    },
    {
        "missing_claims": [
            {
                "type": "comparison",
                "concept": "",
                "statement": "Synthetic proposition.",
                "parameterisation": None,
            }
        ]
    },
    {
        "missing_claims": [
            {
                "type": "comparison",
                "concept": "example",
                "statement": "",
                "parameterisation": None,
            }
        ]
    },
]

for output in bad_outputs:
    try:
        coverage.build_claim_coverage(
            answer_draft=ANSWER,
            existing_claims=EXISTING,
            assessor_output=output,
        )
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError(
            f"Malformed coverage output was accepted: {output!r}"
        )

print("PASS: malformed or authority-bearing assessor output is rejected")


print("\n[7] injected assessor receives only bounded prompt and schema")

captured = {}


def fake_assessor(*, prompt, schema):
    captured["prompt"] = prompt
    captured["schema"] = schema
    return {"missing_claims": []}


assessed = coverage.assess_claim_coverage(
    answer_draft=ANSWER,
    existing_claims=EXISTING,
    assessor=fake_assessor,
)

assert assessed.missing_claims == []
assert captured["schema"] == coverage.claim_coverage_output_schema()
assert ANSWER in captured["prompt"]

print("PASS: injected assessor output becomes application-owned coverage result")


print("\n[8] application-discovered coverage is not capped at five claims")

six_missing = {
    "missing_claims": [
        {
            "type": "methodological",
            "concept": f"concept {i}",
            "statement": f"Material checkable proposition {i}.",
            "parameterisation": None,
        }
        for i in range(6)
    ]
}

six_result = coverage.build_claim_coverage(
    answer_draft=ANSWER,
    existing_claims=[],
    assessor_output=six_missing,
)

assert len(six_result.missing_claims) == 6

print("PASS: coverage layer has no arbitrary five-claim assessment ceiling")



print("\n[9] representation requires the same material proposition")

representation_prompt = coverage.build_claim_coverage_prompt(
    answer_draft=ANSWER,
    existing_claims=EXISTING,
)

normalized_representation = " ".join(
    representation_prompt.lower().split()
)

assert "same material proposition" in normalized_representation
assert "same topic or concept is not enough" in normalized_representation
assert "frequency" in normalized_representation
assert "qualifier" in normalized_representation
assert "direction" in normalized_representation

print("PASS: prompt distinguishes topic overlap from proposition coverage")

print("\nAll academic claim-coverage contract checks passed.")
