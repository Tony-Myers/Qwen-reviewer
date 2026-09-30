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


print("\n[10] coverage assessment distinguishes established outcomes")

missing_assessment = coverage.ClaimCoverageAssessment.from_result(
    coverage.ClaimCoverageResult(
        missing_claims=[
            academic_chat.TechnicalClaim(
                type="methodological",
                concept="missing proposition",
                statement="A material proposition was omitted.",
                parameterisation=None,
            )
        ]
    )
)

assert missing_assessment.status == "missing_claims_found"
assert missing_assessment.result is not None
assert len(missing_assessment.result.missing_claims) == 1
assert missing_assessment.reasons == []

empty_assessment = coverage.ClaimCoverageAssessment.from_result(
    coverage.ClaimCoverageResult(missing_claims=[])
)

assert empty_assessment.status == "no_missing_claims_proposed"
assert empty_assessment.result is not None
assert empty_assessment.result.missing_claims == []
assert empty_assessment.reasons == []

print("PASS: successful coverage distinguishes omissions from no omissions proposed")


print("\n[11] unavailable coverage is distinct from an empty result")

unavailable_assessment = coverage.ClaimCoverageAssessment.unavailable(
    "Local coverage assessment could not be established."
)

assert unavailable_assessment.status == "coverage_assessment_unavailable"
assert unavailable_assessment.result is None
assert unavailable_assessment.reasons == [
    "Local coverage assessment could not be established."
]

assert unavailable_assessment.status != empty_assessment.status
assert unavailable_assessment.result != empty_assessment.result

print("PASS: unavailable coverage cannot masquerade as zero omissions")


print("\n[12] coverage assessment serialises without overstating completeness")

missing_payload = missing_assessment.to_dict()
empty_payload = empty_assessment.to_dict()
unavailable_payload = unavailable_assessment.to_dict()

assert missing_payload["status"] == "missing_claims_found"
assert len(missing_payload["missing_claims"]) == 1
assert missing_payload["reasons"] == []

assert empty_payload == {
    "status": "no_missing_claims_proposed",
    "missing_claims": [],
    "reasons": [],
}

assert unavailable_payload == {
    "status": "coverage_assessment_unavailable",
    "missing_claims": None,
    "reasons": [
        "Local coverage assessment could not be established."
    ],
}

assert "complete" not in repr(empty_payload).lower()

print("PASS: coverage serialisation reports proposal state, not verified completeness")



print("\n[13] unattempted coverage is distinct from unavailable coverage")

not_attempted_assessment = coverage.ClaimCoverageAssessment.not_attempted(
    "No coverage assessor was supplied."
)

assert not_attempted_assessment.status == "coverage_not_attempted"
assert not_attempted_assessment.result is None
assert not_attempted_assessment.reasons == [
    "No coverage assessor was supplied."
]

assert (
    not_attempted_assessment.status
    != unavailable_assessment.status
)
assert (
    not_attempted_assessment.status
    != empty_assessment.status
)

assert not_attempted_assessment.to_dict() == {
    "status": "coverage_not_attempted",
    "missing_claims": None,
    "reasons": ["No coverage assessor was supplied."],
}

print("PASS: unattempted coverage remains distinct from failed assessment")



print("\n[14] untrusted coverage output has a dedicated failure type")

malformed_outputs = [
    {},
    {"missing_claims": "not-an-array"},
    {
        "missing_claims": [
            {
                "type": "methodological",
                "concept": "HDI width",
                "statement": "",
                "parameterisation": None,
            }
        ]
    },
    {
        "missing_claims": [],
        "verification": "technically_verified",
    },
]

for malformed_output in malformed_outputs:
    try:
        coverage.build_claim_coverage(
            answer_draft="Synthetic answer.",
            existing_claims=[],
            assessor_output=malformed_output,
        )
    except coverage.ClaimCoverageOutputError:
        pass
    else:
        raise AssertionError(
            f"Malformed assessor output did not raise "
            f"ClaimCoverageOutputError: {malformed_output!r}"
        )

print("PASS: malformed untrusted coverage output has a dedicated exception")


print("\n[15] trusted coverage input errors remain ordinary contract errors")

try:
    coverage.build_claim_coverage(
        answer_draft="",
        existing_claims=[],
        assessor_output={"missing_claims": []},
    )
except ValueError as exc:
    assert not isinstance(exc, coverage.ClaimCoverageOutputError)
else:
    raise AssertionError("Empty trusted answer_draft was accepted.")

print("PASS: trusted input failure is not misclassified as assessor-output failure")


print("\nAll academic claim-coverage contract checks passed.")


print("\n[16] coverage prompt exposes embedded propositions atomically")

embedded_answer = """
The adjusted model often gives smaller estimates because the additional
covariate accounts for part of the association. In some datasets the
difference may be negligible. A smaller estimate is not automatically more
accurate or preferable. Therefore, analysts should choose the adjusted model
when the covariate is scientifically relevant.
""".strip()

embedded_prompt = coverage.build_claim_coverage_prompt(
    answer_draft=embedded_answer,
    existing_claims=[],
)

embedded_normalized = " ".join(embedded_prompt.lower().split())

required_fragments = [
    "explanatory prose can contain",
    "qualifiers or frequency statements",
    "comparative or conditional statements",
    "explanatory, inferential, causal, or mechanistic links",
    "interpretive conclusions",
    "recommendations or preferences",
    "independently differ in support or correctness",
]

for fragment in required_fragments:
    assert fragment in embedded_normalized, fragment

print(
    "PASS: coverage prompt distinguishes explanatory prose from "
    "embedded checkable propositions"
)
print(
    "PASS: coverage prompt requires independently assessable "
    "propositions to remain atomic"
)


print("\n[17] pure discovery schema exposes discovered claims only")

discovery_schema = coverage.claim_discovery_output_schema()

assert set(discovery_schema) == {
    "type",
    "properties",
    "required",
    "additionalProperties",
}
assert discovery_schema["required"] == ["discovered_claims"]
assert discovery_schema["additionalProperties"] is False

discovered_schema = discovery_schema["properties"]["discovered_claims"]
assert discovered_schema["type"] == "array"

discovered_item = discovered_schema["items"]
assert set(discovered_item["required"]) == {
    "type",
    "concept",
    "statement",
    "parameterisation",
    "source_anchor",
}
assert discovered_item["properties"]["source_anchor"] == {
    "type": "string",
    "minLength": 1,
}
assert discovered_item["additionalProperties"] is False

print("PASS: discovery schema is structurally bounded")


print("\n[18] pure discovery sees answer but not existing claims")

discovery_prompt = coverage.build_claim_discovery_prompt(
    answer_draft=embedded_answer,
)

discovery_normalized = " ".join(
    discovery_prompt.lower().split()
)

assert embedded_answer in discovery_prompt
assert "EXISTING TECHNICAL CLAIMS" not in discovery_prompt
assert "already represented" not in discovery_normalized
assert "missing claim" not in discovery_normalized
assert "deduplic" not in discovery_normalized

for fragment in required_fragments:
    assert fragment in discovery_normalized, fragment

assert "do not judge whether" in discovery_normalized
assert "true" in discovery_normalized
assert "false" in discovery_normalized

print("PASS: discovery is independent of representation assessment")


print("\n[19] injected discovery assessor produces application-owned claims")

discovery_captured = {}

recommendation_anchor = "covariate is scientifically relevant"
interpretation_anchor = "accurate or preferable"


def fake_discovery_assessor(*, prompt, schema):
    discovery_captured["prompt"] = prompt
    discovery_captured["schema"] = schema
    return {
        "discovered_claims": [
            {
                "type": "recommendation",
                "concept": "model selection",
                "statement": (
                    "Analysts should choose the adjusted model when "
                    "the covariate is scientifically relevant."
                ),
                "parameterisation": None,
                "source_anchor": recommendation_anchor,
            },
            {
                "type": "interpretation",
                "concept": "estimate size",
                "statement": (
                    "A smaller estimate is not automatically more "
                    "accurate or preferable."
                ),
                "parameterisation": None,
                "source_anchor": interpretation_anchor,
            },
        ]
    }


discovered = coverage.discover_answer_claims(
    answer_draft=embedded_answer,
    assessor=fake_discovery_assessor,
)

assert len(discovered) == 2
assert all(
    isinstance(item, coverage.DiscoveredClaim)
    for item in discovered
)
assert all(
    isinstance(item.claim, academic_chat.TechnicalClaim)
    for item in discovered
)
assert discovered[0].claim.statement == (
    "Analysts should choose the adjusted model when "
    "the covariate is scientifically relevant."
)
assert discovered[0].source_anchor == recommendation_anchor
assert discovered[0].source_start == embedded_answer.index(
    recommendation_anchor
)
assert discovered[0].source_end == (
    discovered[0].source_start + len(recommendation_anchor)
)
assert discovered[1].claim.statement == (
    "A smaller estimate is not automatically more "
    "accurate or preferable."
)
assert discovered[1].source_anchor == interpretation_anchor
assert discovered[1].source_start == embedded_answer.index(
    interpretation_anchor
)
assert discovered[1].source_end == (
    discovered[1].source_start + len(interpretation_anchor)
)
assert discovery_captured["schema"] == (
    coverage.claim_discovery_output_schema()
)
assert embedded_answer in discovery_captured["prompt"]

print(
    "PASS: pure discovery returns application-owned claims "
    "with verified provenance"
)


print("\n[20] representation schema exposes decision and source index only")

representation_schema = coverage.claim_representation_output_schema()

assert set(representation_schema) == {
    "type",
    "properties",
    "required",
    "additionalProperties",
}
assert set(representation_schema["required"]) == {
    "represented",
    "represented_by",
}
assert representation_schema["additionalProperties"] is False

assert representation_schema["properties"]["represented"] == {
    "type": "boolean"
}
assert representation_schema["properties"]["represented_by"] == {
    "type": ["integer", "null"]
}

print("PASS: representation schema is structurally bounded")


print("\n[21] representation prompt sees candidate and existing claims only")

candidate = academic_chat.TechnicalClaim(
    type="comparison",
    concept="interval width",
    statement=(
        "In some skewed distributions, the HDI may be narrower "
        "than the ETI."
    ),
    parameterisation=None,
)

representation_prompt = coverage.build_claim_representation_prompt(
    candidate_claim=candidate,
    existing_claims=EXISTING,
)

representation_normalized = " ".join(
    representation_prompt.lower().split()
)

assert candidate.statement in representation_prompt
assert EXISTING[0].statement in representation_prompt
assert f"type: {candidate.type}" not in representation_prompt
assert f"concept: {candidate.concept}" not in representation_prompt
assert f"type: {EXISTING[0].type}" not in representation_prompt
assert f"concept: {EXISTING[0].concept}" not in representation_prompt
assert "answer draft" not in representation_normalized
assert "same material proposition" in representation_normalized
assert "sharing the same topic" in representation_normalized
assert "broader related claim" in representation_normalized
assert "do not judge whether" in representation_normalized
assert "true" in representation_normalized
assert "false" in representation_normalized

print("PASS: representation assessment has a bounded proposition-level role")


print("\n[22] representation decisions are validated application state")

represented_candidate = academic_chat.TechnicalClaim(
    type="methodological",
    concept="same proposition",
    statement="The relative widths depend on distribution shape.",
    parameterisation=None,
)

represented = coverage.build_claim_representation(
    candidate_claim=represented_candidate,
    existing_claims=EXISTING,
    assessor_output={
        "represented": True,
        "represented_by": 1,
    },
)

assert represented.represented is True
assert represented.represented_by == 1

not_represented = coverage.build_claim_representation(
    candidate_claim=candidate,
    existing_claims=EXISTING,
    assessor_output={
        "represented": False,
        "represented_by": None,
    },
)

assert not_represented.represented is False
assert not_represented.represented_by is None

print("PASS: representation decisions become validated application state")


print("\n[23] invalid representation output cannot establish suppression")

invalid_representation_outputs = [
    {},
    {
        "represented": True,
        "represented_by": None,
    },
    {
        "represented": False,
        "represented_by": 1,
    },
    {
        "represented": True,
        "represented_by": 0,
    },
    {
        "represented": True,
        "represented_by": len(EXISTING) + 1,
    },
    {
        "represented": "yes",
        "represented_by": 1,
    },
    {
        "represented": True,
        "represented_by": 1,
        "confidence": 0.99,
    },
]

for invalid_output in invalid_representation_outputs:
    try:
        coverage.build_claim_representation(
            candidate_claim=candidate,
            existing_claims=EXISTING,
            assessor_output=invalid_output,
        )
    except coverage.ClaimCoverageOutputError:
        pass
    else:
        raise AssertionError(
            "Invalid representation output was accepted: "
            f"{invalid_output!r}"
        )

print("PASS: malformed representation cannot establish claim suppression")


print("\n[24] injected representation assessor receives bounded prompt and schema")

representation_captured = {}


def fake_representation_assessor(*, prompt, schema):
    representation_captured["prompt"] = prompt
    representation_captured["schema"] = schema
    return {
        "represented": False,
        "represented_by": None,
    }


representation_assessment = coverage.assess_claim_representation(
    candidate_claim=candidate,
    existing_claims=EXISTING,
    assessor=fake_representation_assessor,
)

assert representation_assessment.represented is False
assert representation_assessment.represented_by is None
assert representation_captured["schema"] == (
    coverage.claim_representation_output_schema()
)
assert candidate.statement in representation_captured["prompt"]

print("PASS: injected representation assessor has bounded proposition-level input")


print("\n[25] exact duplicate is suppressed without semantic assessment")

exact_duplicate = EXISTING[0]
semantic_calls = []


def should_not_be_called(*, candidate_claim, existing_claims):
    semantic_calls.append(candidate_claim)
    raise AssertionError(
        "Semantic representation assessor was called for an exact duplicate."
    )


exact_filtered = coverage.filter_discovered_claims(
    discovered_claims=[exact_duplicate],
    existing_claims=EXISTING,
    representation_assessor=should_not_be_called,
)

assert exact_filtered == []
assert semantic_calls == []

print("PASS: exact duplicates are suppressed deterministically")


print("\n[26] only established semantic representation suppresses a candidate")

represented_semantically = academic_chat.TechnicalClaim(
    type="methodological",
    concept="relative interval width",
    statement=(
        "The relative widths of the HDI and ETI depend on "
        "the shape of the posterior distribution."
    ),
    parameterisation=None,
)

novel_semantically = academic_chat.TechnicalClaim(
    type="comparative",
    concept="HDI sometimes narrower",
    statement=(
        "In some skewed distributions, the HDI may be narrower "
        "than the ETI."
    ),
    parameterisation=None,
)


def semantic_representation(*, candidate_claim, existing_claims):
    if candidate_claim is represented_semantically:
        return coverage.ClaimRepresentation(
            represented=True,
            represented_by=1,
        )

    return coverage.ClaimRepresentation(
        represented=False,
        represented_by=None,
    )


semantic_filtered = coverage.filter_discovered_claims(
    discovered_claims=[
        represented_semantically,
        novel_semantically,
    ],
    existing_claims=EXISTING,
    representation_assessor=semantic_representation,
)

assert semantic_filtered == [novel_semantically]

print("PASS: only established semantic representation suppresses a claim")


print("\n[27] invalid representation output fails open into checking")

fail_open_candidate = academic_chat.TechnicalClaim(
    type="interpretive",
    concept="precision",
    statement=(
        "A narrower HDI is not automatically more precise or preferable."
    ),
    parameterisation=None,
)


def invalid_representation(*, candidate_claim, existing_claims):
    raise coverage.ClaimCoverageOutputError(
        "Synthetic malformed representation output."
    )


fail_open_filtered = coverage.filter_discovered_claims(
    discovered_claims=[fail_open_candidate],
    existing_claims=EXISTING,
    representation_assessor=invalid_representation,
)

assert fail_open_filtered == [fail_open_candidate]

print("PASS: invalid representation retains candidate for checking")


print("\n[28] unexpected representation faults still propagate")


def broken_representation(*, candidate_claim, existing_claims):
    raise TypeError("Synthetic programming fault.")


try:
    coverage.filter_discovered_claims(
        discovered_claims=[fail_open_candidate],
        existing_claims=EXISTING,
        representation_assessor=broken_representation,
    )
except TypeError as exc:
    assert "Synthetic programming fault" in str(exc)
else:
    raise AssertionError(
        "Unexpected representation fault was swallowed."
    )

print("PASS: unexpected representation faults are not hidden")


print("\n[29] two-stage coverage separates discovery from representation")

two_stage_answer = """
For symmetric posteriors the two intervals may be similar. In some skewed
posteriors the HDI may be narrower than the ETI. A narrower interval is not
automatically preferable.
""".strip()

two_stage_existing = [
    academic_chat.TechnicalClaim(
        type="comparative",
        concept="interval similarity",
        statement=(
            "For symmetric posteriors the ETI and HDI may be similar."
        ),
        parameterisation=None,
    )
]

discovery_prompts = []
representation_candidates = []


def two_stage_assessor(*, prompt, schema):
    if (
        schema == coverage.claim_discovery_output_schema()
        and "ANSWER DRAFT" in prompt
    ):
        discovery_prompts.append(prompt)
        return {
            "discovered_claims": [
                {
                    "type": "comparative",
                    "concept": "interval similarity",
                    "statement": (
                        "For symmetric posteriors the ETI and HDI "
                        "may be similar."
                    ),
                    "parameterisation": None,
                    "source_anchor": "two intervals may be similar",
                },
                {
                    "type": "comparative",
                    "concept": "interval width",
                    "statement": (
                        "In some skewed posteriors the HDI may be "
                        "narrower than the ETI."
                    ),
                    "parameterisation": None,
                    "source_anchor": "HDI may be narrower than the ETI",
                },
                {
                    "type": "interpretive",
                    "concept": "interval preference",
                    "statement": (
                        "A narrower interval is not automatically preferable."
                    ),
                    "parameterisation": None,
                    "source_anchor": "automatically preferable",
                },
            ]
        }

    if (
        schema == coverage.claim_discovery_output_schema()
        and "SOURCE SENTENCE" in prompt
    ):
        return {"discovered_claims": []}

    if schema == coverage.claim_decomposition_output_schema():
        return {
            "requires_decomposition": False,
            "atomic_claims": [],
        }

    if schema == coverage.claim_representation_output_schema():
        if "HDI may be narrower than the ETI" in prompt:
            representation_candidates.append("width")
            return {
                "represented": False,
                "represented_by": None,
            }

        if "not automatically preferable" in prompt:
            representation_candidates.append("preference")
            return {
                "represented": False,
                "represented_by": None,
            }

        raise AssertionError(
            "Exact duplicate unexpectedly reached semantic representation."
        )

    raise AssertionError("Unexpected schema supplied to two-stage assessor.")


two_stage_result = coverage.assess_claim_coverage_two_stage(
    answer_draft=two_stage_answer,
    existing_claims=two_stage_existing,
    assessor=two_stage_assessor,
)

assert len(discovery_prompts) == 1
assert two_stage_answer in discovery_prompts[0]
assert "EXISTING TECHNICAL CLAIMS" not in discovery_prompts[0]

assert representation_candidates == [
    "width",
    "preference",
]

assert [
    claim.statement
    for claim in two_stage_result.missing_claims
] == [
    (
        "In some skewed posteriors the HDI may be "
        "narrower than the ETI."
    ),
    "A narrower interval is not automatically preferable.",
]

print("PASS: discovery and representation remain separate in composition")


print("\n[29b] two-stage coverage retains the independent atomic discovery set")

assert all(
    isinstance(discovered, coverage.DiscoveredClaim)
    for discovered in two_stage_result.discovered_claims
)

assert [
    discovered.claim.statement
    for discovered in two_stage_result.discovered_claims
] == [
    "For symmetric posteriors the ETI and HDI may be similar.",
    (
        "In some skewed posteriors the HDI may be "
        "narrower than the ETI."
    ),
    "A narrower interval is not automatically preferable.",
]

for discovered in two_stage_result.discovered_claims:
    assert (
        two_stage_answer[
            discovered.source_start:discovered.source_end
        ]
        == discovered.source_anchor
    )

assert [
    claim.statement
    for claim in two_stage_result.missing_claims
] == [
    (
        "In some skewed posteriors the HDI may be "
        "narrower than the ETI."
    ),
    "A narrower interval is not automatically preferable.",
]

print("PASS: independent discovery is retained separately from missing claims")


print("\n[30] two-stage coverage retains malformed representation candidates")

malformed_candidate_statement = (
    "A narrower interval is not automatically more precise."
)


def malformed_two_stage_assessor(*, prompt, schema):
    if (
        schema == coverage.claim_discovery_output_schema()
        and "ANSWER DRAFT" in prompt
    ):
        return {
            "discovered_claims": [
                {
                    "type": "interpretive",
                    "concept": "precision",
                    "statement": malformed_candidate_statement,
                    "parameterisation": None,
                    "source_anchor": malformed_candidate_statement,
                }
            ]
        }

    if (
        schema == coverage.claim_discovery_output_schema()
        and "SOURCE SENTENCE" in prompt
    ):
        return {"discovered_claims": []}

    if schema == coverage.claim_decomposition_output_schema():
        return {
            "requires_decomposition": False,
            "atomic_claims": [],
        }

    if schema == coverage.claim_representation_output_schema():
        return {
            "represented": True,
            "represented_by": None,
        }

    raise AssertionError("Unexpected schema.")


malformed_two_stage = coverage.assess_claim_coverage_two_stage(
    answer_draft=malformed_candidate_statement,
    existing_claims=two_stage_existing,
    assessor=malformed_two_stage_assessor,
)

assert [
    claim.statement
    for claim in malformed_two_stage.missing_claims
] == [malformed_candidate_statement]

print("PASS: malformed representation fails open into downstream checking")


print("\n[31] discovery failure still fails the coverage assessment")


def malformed_discovery_assessor(*, prompt, schema):
    if schema == coverage.claim_discovery_output_schema():
        return {
            "discovered_claims": "not-an-array",
        }

    raise AssertionError(
        "Representation must not run after malformed discovery."
    )


try:
    coverage.assess_claim_coverage_two_stage(
        answer_draft=two_stage_answer,
        existing_claims=two_stage_existing,
        assessor=malformed_discovery_assessor,
    )
except coverage.ClaimCoverageOutputError:
    pass
else:
    raise AssertionError(
        "Malformed discovery was treated as successful coverage."
    )

print("PASS: discovery failure cannot masquerade as successful coverage")


print("\n[32] unexpected representation fault propagates from two-stage coverage")

broken_two_stage_answer = malformed_candidate_statement


def broken_two_stage_assessor(*, prompt, schema):
    if schema == coverage.claim_discovery_output_schema():
        return {
            "discovered_claims": [
                {
                    "type": "interpretive",
                    "concept": "precision",
                    "statement": malformed_candidate_statement,
                    "parameterisation": None,
                    "source_anchor": malformed_candidate_statement,
                }
            ]
        }

    if schema == coverage.claim_decomposition_output_schema():
        return {
            "requires_decomposition": False,
            "atomic_claims": [],
        }

    if schema == coverage.claim_representation_output_schema():
        raise TypeError("Synthetic two-stage programming fault.")

    raise AssertionError("Unexpected schema.")


try:
    coverage.assess_claim_coverage_two_stage(
        answer_draft=broken_two_stage_answer,
        existing_claims=two_stage_existing,
        assessor=broken_two_stage_assessor,
    )
except TypeError as exc:
    assert "Synthetic two-stage programming fault" in str(exc)
else:
    raise AssertionError(
        "Unexpected two-stage representation fault was swallowed."
    )

print("PASS: unexpected two-stage faults remain visible")

print("\n[29c] claim discovery resolves a unique verbatim source anchor")

rct_context_answer = (
    "In randomised trials, the primary rationale for covariate adjustment "
    "is statistical efficiency, not confounding control. Adjusting for "
    "baseline variables that strongly predict the outcome reduces residual "
    "variation, narrows confidence intervals, and increases power."
)

rct_source_anchor = "narrows confidence intervals, and increases power"

rct_discovery_output = {
    "discovered_claims": [
        {
            "type": "methodological",
            "concept": "covariate adjustment",
            "statement": (
                "Adjusting for baseline variables that strongly predict "
                "the outcome increases power."
            ),
            "parameterisation": None,
            "source_anchor": rct_source_anchor,
        }
    ]
}


def rct_provenance_assessor(*, prompt, schema):
    assert rct_context_answer in prompt
    return rct_discovery_output


rct_discovered = coverage.discover_answer_claims(
    answer_draft=rct_context_answer,
    assessor=rct_provenance_assessor,
)

assert len(rct_discovered) == 1
assert rct_discovered[0].claim.statement == (
    "Adjusting for baseline variables that strongly predict "
    "the outcome increases power."
)
assert rct_discovered[0].source_anchor == rct_source_anchor
assert rct_discovered[0].source_start == rct_context_answer.index(
    rct_source_anchor
)
assert rct_discovered[0].source_end == (
    rct_discovered[0].source_start + len(rct_source_anchor)
)

print("PASS: unique verbatim source anchor resolves to exact answer position")


print("\n[29d] claim discovery rejects missing or ambiguous source anchors")


def missing_anchor_assessor(*, prompt, schema):
    return {
        "discovered_claims": [
            {
                "type": "methodological",
                "concept": "covariate adjustment",
                "statement": (
                    "Adjusting for baseline variables that strongly predict "
                    "the outcome increases power."
                ),
                "parameterisation": None,
                "source_anchor": "text that is not in the answer",
            }
        ]
    }


try:
    coverage.discover_answer_claims(
        answer_draft=rct_context_answer,
        assessor=missing_anchor_assessor,
    )
except coverage.ClaimCoverageOutputError:
    pass
else:
    raise AssertionError(
        "Missing discovery source anchor was unexpectedly accepted."
    )


ambiguous_answer = (
    "Adjustment increases power in one setting. "
    "Adjustment increases power in another setting."
)


def ambiguous_anchor_assessor(*, prompt, schema):
    return {
        "discovered_claims": [
            {
                "type": "methodological",
                "concept": "power",
                "statement": "Adjustment can increase power.",
                "parameterisation": None,
                "source_anchor": "increases power",
            }
        ]
    }


try:
    coverage.discover_answer_claims(
        answer_draft=ambiguous_answer,
        assessor=ambiguous_anchor_assessor,
    )
except coverage.ClaimCoverageOutputError:
    pass
else:
    raise AssertionError(
        "Ambiguous discovery source anchor was unexpectedly accepted."
    )

print("PASS: missing and ambiguous source anchors are rejected")


print("\n[29e] verified anchor resolves to source sentence and preceding context")

rct_source_sentence = (
    "Adjusting for baseline variables that strongly predict the outcome "
    "reduces residual variation, narrows confidence intervals, and "
    "increases power."
)
rct_preceding_sentence = (
    "In randomised trials, the primary rationale for covariate adjustment "
    "is statistical efficiency, not confounding control."
)

rct_provenance = coverage.resolve_claim_source_context(
    answer_draft=rct_context_answer,
    source_start=rct_discovered[0].source_start,
    source_end=rct_discovered[0].source_end,
)

assert rct_provenance.source_sentence == rct_source_sentence
assert rct_provenance.source_sentence_start == (
    rct_context_answer.index(rct_source_sentence)
)
assert rct_provenance.source_sentence_end == (
    rct_provenance.source_sentence_start + len(rct_source_sentence)
)
assert rct_provenance.context_excerpt == (
    rct_preceding_sentence + " " + rct_source_sentence
)
assert rct_provenance.context_start == 0
assert rct_provenance.context_end == len(rct_context_answer)

print(
    "PASS: application resolves exact source sentence and bounded "
    "preceding context"
)


print("\n[29f] statistical decimals do not create false sentence boundaries")

statistical_answer = (
    "The baseline age difference was statistically significant "
    "(p = .03). The adjusted analysis gave p = 0.04 for the treatment "
    "effect. This result was interpreted cautiously."
)
statistical_anchor = "adjusted analysis gave p = 0.04"

statistical_start = statistical_answer.index(statistical_anchor)
statistical_end = statistical_start + len(statistical_anchor)

statistical_provenance = coverage.resolve_claim_source_context(
    answer_draft=statistical_answer,
    source_start=statistical_start,
    source_end=statistical_end,
)

assert statistical_provenance.source_sentence == (
    "The adjusted analysis gave p = 0.04 for the treatment effect."
)
assert statistical_provenance.context_excerpt == (
    "The baseline age difference was statistically significant "
    "(p = .03). The adjusted analysis gave p = 0.04 for the treatment "
    "effect."
)

print("PASS: statistical decimal punctuation preserves sentence provenance")


print("\n[29g] first-sentence source uses only its own sentence as context")

first_sentence_answer = (
    "Adjustment can improve precision. "
    "The second sentence adds unrelated detail."
)
first_sentence_anchor = "improve precision"
first_sentence_start = first_sentence_answer.index(first_sentence_anchor)

first_sentence_provenance = coverage.resolve_claim_source_context(
    answer_draft=first_sentence_answer,
    source_start=first_sentence_start,
    source_end=first_sentence_start + len(first_sentence_anchor),
)

assert first_sentence_provenance.source_sentence == (
    "Adjustment can improve precision."
)
assert first_sentence_provenance.context_excerpt == (
    "Adjustment can improve precision."
)
assert first_sentence_provenance.source_sentence_start == 0
assert first_sentence_provenance.context_start == 0

print("PASS: first-sentence provenance does not invent preceding context")


print("\n[29h] invalid and cross-sentence source spans are rejected")

try:
    coverage.resolve_claim_source_context(
        answer_draft=first_sentence_answer,
        source_start=-1,
        source_end=5,
    )
except ValueError:
    pass
else:
    raise AssertionError("Negative source span was unexpectedly accepted.")

cross_sentence_start = first_sentence_answer.index("precision")
cross_sentence_end = (
    first_sentence_answer.index("second sentence")
    + len("second sentence")
)

try:
    coverage.resolve_claim_source_context(
        answer_draft=first_sentence_answer,
        source_start=cross_sentence_start,
        source_end=cross_sentence_end,
    )
except ValueError:
    pass
else:
    raise AssertionError(
        "Cross-sentence source span was unexpectedly accepted."
    )

print("PASS: invalid and cross-sentence provenance spans are rejected")


print("\n[33] restriction schema exposes only the omission decision")

restriction_schema = coverage.material_restriction_output_schema()

assert restriction_schema["type"] == "object"
assert set(restriction_schema["properties"]) == {
    "material_restriction_omitted"
}
assert restriction_schema["required"] == [
    "material_restriction_omitted"
]
assert restriction_schema["additionalProperties"] is False
assert restriction_schema["properties"]["material_restriction_omitted"] == {
    "type": "boolean",
}

print("PASS: restriction schema grants no repair or methodological authority")


print("\n[34] restriction prompt has a bounded source-comparison role")

rct_restriction_claim = academic_chat.TechnicalClaim(
    type="GENERATED-TYPE-MUST-NOT-AUTHORISE-SEMANTICS",
    concept="GENERATED-CONCEPT-MUST-NOT-AUTHORISE-SEMANTICS",
    statement=(
        "Adjusting for baseline variables that strongly predict the outcome "
        "increases power."
    ),
    parameterisation="strongly predictive baseline variables",
)

rct_restriction_source = coverage.resolve_claim_source_context(
    answer_draft=rct_context_answer,
    source_start=rct_discovered[0].source_start,
    source_end=rct_discovered[0].source_end,
)

restriction_prompt = coverage.build_material_restriction_prompt(
    candidate_claim=rct_restriction_claim,
    source_context=rct_restriction_source,
)

assert rct_restriction_claim.statement in restriction_prompt
assert rct_restriction_claim.parameterisation in restriction_prompt
assert rct_restriction_claim.type not in restriction_prompt
assert rct_restriction_claim.concept not in restriction_prompt
assert rct_restriction_source.source_sentence in restriction_prompt
assert rct_restriction_source.context_excerpt in restriction_prompt
assert "outside knowledge" in restriction_prompt.lower()
assert "scientifically correct" in restriction_prompt.lower()
assert "scope" in restriction_prompt.lower()
assert "condition" in restriction_prompt.lower()
assert "population" in restriction_prompt.lower()
assert "study design" in restriction_prompt.lower()
assert "referent" in restriction_prompt.lower()
assert "modality" in restriction_prompt.lower()
assert "direction" in restriction_prompt.lower()
assert "parameterisation" in restriction_prompt.lower()
assert "govern" in restriction_prompt.lower()
assert "merely because" in restriction_prompt.lower()
assert "pronoun" in restriction_prompt.lower()
assert "explicit antecedent" in restriction_prompt.lower()
assert "referential explicitness" in restriction_prompt.lower()
assert "actually loses a material" in restriction_prompt.lower()

print("PASS: restriction prompt asks only about material omission")


print("\n[35] material restriction loss can be represented explicitly")

rct_scope_loss = coverage.build_material_restriction_assessment(
    candidate_claim=rct_restriction_claim,
    source_context=rct_restriction_source,
    assessor_output={"material_restriction_omitted": True},
)

assert rct_scope_loss.material_restriction_omitted is True

print("PASS: material restriction loss is application-owned state")


print("\n[36] preserved proposition has no material restriction omission")

scoped_rct_claim = academic_chat.TechnicalClaim(
    type="statistical_mechanism",
    concept="effect_of_predictive_covariates",
    statement=(
        "In randomised trials, adjusting for baseline variables that strongly "
        "predict the outcome increases power."
    ),
    parameterisation=None,
)

rct_scope_preserved = coverage.build_material_restriction_assessment(
    candidate_claim=scoped_rct_claim,
    source_context=rct_restriction_source,
    assessor_output={"material_restriction_omitted": False},
)

assert rct_scope_preserved.material_restriction_omitted is False

print("PASS: absence of material restriction loss is represented explicitly")


print("\n[37] restriction output cannot acquire repair or reasoning authority")

for malformed_restriction_output in (
    {
        "material_restriction_omitted": True,
        "corrected_claim": (
            "In randomised trials, adjustment increases power."
        ),
    },
    {
        "material_restriction_omitted": True,
        "reason": "The RCT condition was omitted.",
    },
    {
        "material_restriction_omitted": "true",
    },
):
    try:
        coverage.build_material_restriction_assessment(
            candidate_claim=rct_restriction_claim,
            source_context=rct_restriction_source,
            assessor_output=malformed_restriction_output,
        )
    except coverage.MaterialRestrictionOutputError:
        pass
    else:
        raise AssertionError(
            "Malformed or authority-bearing restriction output was accepted."
        )

print("PASS: restriction assessor cannot rewrite or explain the claim")


print("\n[38] injected restriction assessor receives bounded comparison input")

captured_restriction_call = {}


def injected_restriction_assessor(*, prompt, schema):
    captured_restriction_call["prompt"] = prompt
    captured_restriction_call["schema"] = schema
    return {"material_restriction_omitted": True}


assessed_restriction = coverage.assess_material_restriction(
    candidate_claim=rct_restriction_claim,
    source_context=rct_restriction_source,
    assessor=injected_restriction_assessor,
)

assert assessed_restriction.material_restriction_omitted is True
assert captured_restriction_call["schema"] == (
    coverage.material_restriction_output_schema()
)
assert rct_restriction_claim.statement in captured_restriction_call["prompt"]
assert (
    rct_restriction_source.source_sentence
    in captured_restriction_call["prompt"]
)
assert (
    rct_restriction_source.context_excerpt
    in captured_restriction_call["prompt"]
)

print("PASS: injected restriction assessor remains proposition-and-source bounded")


print("\n[39] sentence spans are application-owned and reusable")

sentence_answer = (
    "First statistical proposition. "
    "Second methodological proposition! "
    "Third proposition without terminal punctuation"
)
sentence_spans = coverage.answer_sentence_spans(sentence_answer)
sentence_texts = [
    sentence_answer[start:end]
    for start, end in sentence_spans
]

assert sentence_texts == [
    "First statistical proposition.",
    "Second methodological proposition!",
    "Third proposition without terminal punctuation",
]

second_start, second_end = sentence_spans[1]
second_context = coverage.resolve_claim_source_context(
    answer_draft=sentence_answer,
    source_start=second_start,
    source_end=second_end,
)
assert second_context.source_sentence == (
    "Second methodological proposition!"
)
assert second_context.context_excerpt == (
    "First statistical proposition. "
    "Second methodological proposition!"
)

print("PASS: source context and sentence audit can share sentence spans")


print("\n[40] sentence audit is bounded to recovery of omitted propositions")

audit_sentence = (
    "Under condition X, measure A generally increases, "
    "while measure B is typically lower."
)
already_extracted = [
    academic_chat.TechnicalClaim(
        type="comparison",
        concept="measure B",
        statement="Under condition X, measure B is typically lower.",
        parameterisation="condition X",
    )
]

audit_prompt = coverage.build_claim_sentence_audit_prompt(
    source_sentence=audit_sentence,
    discovered_claims=already_extracted,
)
audit_normalized = " ".join(audit_prompt.lower().split())

assert audit_sentence in audit_prompt
assert already_extracted[0].statement in audit_prompt
assert "additional material propositions" in audit_normalized
assert "not already represented" in audit_normalized
assert "do not judge whether" in audit_normalized
assert "true" in audit_normalized
assert "false" in audit_normalized
assert "qualifiers" in audit_normalized
assert "generally" in audit_normalized
assert "typically" in audit_normalized
assert "primarily" in audit_normalized
assert "keep independently checkable propositions separate" in audit_normalized
assert "source_anchor" in audit_prompt

print("PASS: sentence audit has a bounded omission-recovery contract")

print("\n[41] sentence audit recovers an omitted qualified proposition")

audit_answer = (
    "Under condition X, measure A generally increases, "
    "while measure B is typically lower."
)
audit_anchor_b = "measure B is typically lower"
audit_existing = [
    coverage.DiscoveredClaim(
        claim=academic_chat.TechnicalClaim(
            type="comparison",
            concept="measure B",
            statement="Under condition X, measure B is typically lower.",
            parameterisation="condition X",
        ),
        source_anchor=audit_anchor_b,
        source_start=audit_answer.index(audit_anchor_b),
        source_end=(
            audit_answer.index(audit_anchor_b) + len(audit_anchor_b)
        ),
    )
]
audit_calls = []


def recover_first_proposition(*, prompt, schema):
    audit_calls.append((prompt, schema))
    return {
        "discovered_claims": [
            {
                "type": "conditional",
                "concept": "measure A",
                "statement": (
                    "Under condition X, measure A generally increases."
                ),
                "parameterisation": "condition X",
                "source_anchor": "measure A generally increases",
            }
        ]
    }


audited = coverage.audit_discovered_claims_by_sentence(
    answer_draft=audit_answer,
    discovered_claims=audit_existing,
    assessor=recover_first_proposition,
)

assert len(audited) == 2
assert audited[0] is audit_existing[0]
assert audited[1].claim.statement == (
    "Under condition X, measure A generally increases."
)
assert audited[1].source_anchor == "measure A generally increases"
assert audited[1].source_start == audit_answer.index(
    "measure A generally increases"
)
assert audited[1].source_end == (
    audited[1].source_start + len("measure A generally increases")
)
assert audit_existing[0].claim.statement in audit_calls[0][0]

print("PASS: sentence audit recovers a proposition omitted by global discovery")


print("\n[42] sentence audit can recover a wholly missed sentence")

wholly_missed_answer = (
    "Introductory prose. "
    "Under condition Y, measure C usually decreases."
)
wholly_missed_calls = []


def recover_wholly_missed(*, prompt, schema):
    wholly_missed_calls.append(prompt)

    if "measure C usually decreases" in prompt:
        return {
            "discovered_claims": [
                {
                    "type": "conditional",
                    "concept": "measure C",
                    "statement": (
                        "Under condition Y, measure C usually decreases."
                    ),
                    "parameterisation": "condition Y",
                    "source_anchor": "measure C usually decreases",
                }
            ]
        }

    return {"discovered_claims": []}


wholly_recovered = coverage.audit_discovered_claims_by_sentence(
    answer_draft=wholly_missed_answer,
    discovered_claims=[],
    assessor=recover_wholly_missed,
)

assert len(wholly_missed_calls) == 2
assert len(wholly_recovered) == 1
assert wholly_recovered[0].claim.statement == (
    "Under condition Y, measure C usually decreases."
)
assert wholly_recovered[0].source_start == wholly_missed_answer.index(
    "measure C usually decreases"
)

print("PASS: every sentence is auditable even after total global omission")


print("\n[43] sentence audit exact-deduplicates recovered propositions")

dedup_answer = "Measure D is generally higher."
dedup_anchor = "Measure D is generally higher"
dedup_claim = academic_chat.TechnicalClaim(
    type="comparison",
    concept="measure D",
    statement="Measure D is generally higher.",
    parameterisation=None,
)
dedup_discovered = coverage.DiscoveredClaim(
    claim=dedup_claim,
    source_anchor=dedup_anchor,
    source_start=dedup_answer.index(dedup_anchor),
    source_end=dedup_answer.index(dedup_anchor) + len(dedup_anchor),
)


def recover_duplicate(*, prompt, schema):
    return {
        "discovered_claims": [
            {
                "type": "comparison",
                "concept": "measure D",
                "statement": "Measure D is generally higher.",
                "parameterisation": None,
                "source_anchor": dedup_anchor,
            }
        ]
    }


deduplicated = coverage.audit_discovered_claims_by_sentence(
    answer_draft=dedup_answer,
    discovered_claims=[dedup_discovered],
    assessor=recover_duplicate,
)

assert deduplicated == [dedup_discovered]

print("PASS: sentence audit does not duplicate an exact discovered claim")


print("\n[44] malformed sentence-audit provenance is locally rejected")


def invalid_audit_anchor(*, prompt, schema):
    return {
        "discovered_claims": [
            {
                "type": "comparison",
                "concept": "measure E",
                "statement": "Measure E is higher.",
                "parameterisation": None,
                "source_anchor": "text not present in the sentence",
            }
        ]
    }


invalid_recovery = coverage.audit_discovered_claims_by_sentence(
    answer_draft="Measure E is higher.",
    discovered_claims=[],
    assessor=invalid_audit_anchor,
)

assert invalid_recovery == []

print("PASS: malformed recovery cannot acquire application provenance")


print("\n[44b] malformed recovery does not discard valid audit candidates")

mixed_answer = "Measure E is higher, while measure F is generally lower."


def mixed_audit_output(*, prompt, schema):
    return {
        "discovered_claims": [
            {
                "type": "comparison",
                "concept": "measure E",
                "statement": "Measure E is higher.",
                "parameterisation": None,
                "source_anchor": "anchor absent from sentence",
            },
            {
                "type": "comparison",
                "concept": "measure F",
                "statement": "Measure F is generally lower.",
                "parameterisation": None,
                "source_anchor": "measure F is generally lower",
            },
        ]
    }


mixed_recovery = coverage.audit_discovered_claims_by_sentence(
    answer_draft=mixed_answer,
    discovered_claims=[],
    assessor=mixed_audit_output,
)

assert len(mixed_recovery) == 1
assert mixed_recovery[0].claim.statement == "Measure F is generally lower."
assert mixed_recovery[0].source_anchor == "measure F is generally lower"

print("PASS: malformed recovery is isolated without losing valid recovery")


print("\n[44c] sentence-audit inference failure preserves global discovery")


def failing_sentence_audit(*, prompt, schema):
    raise coverage.ClaimCoverageOutputError(
        "Synthetic sentence-audit inference failure."
    )


audit_failure_result = coverage.audit_discovered_claims_by_sentence(
    answer_draft=dedup_answer,
    discovered_claims=[dedup_discovered],
    assessor=failing_sentence_audit,
)

assert audit_failure_result == [dedup_discovered]

print("PASS: sentence-audit inference failure cannot erase global discovery")


print("\n[44d] malformed sentence-audit envelope preserves global discovery")


def malformed_sentence_audit_envelope(*, prompt, schema):
    return {"discovered_claims": "not-an-array"}


malformed_audit_result = coverage.audit_discovered_claims_by_sentence(
    answer_draft=dedup_answer,
    discovered_claims=[dedup_discovered],
    assessor=malformed_sentence_audit_envelope,
)

assert malformed_audit_result == [dedup_discovered]

print("PASS: malformed sentence-audit envelope cannot erase global discovery")


print("\n[45] two-stage coverage includes sentence-audit recovery before representation")

integrated_answer = (
    "Under condition X, measure A generally increases, "
    "while measure B is typically lower."
)
integrated_calls = []


def integrated_assessor(*, prompt, schema):
    integrated_calls.append(prompt)

    if "ANSWER DRAFT" in prompt:
        return {
            "discovered_claims": [
                {
                    "type": "comparison",
                    "concept": "measure B",
                    "statement": (
                        "Under condition X, measure B is typically lower."
                    ),
                    "parameterisation": "condition X",
                    "source_anchor": "measure B is typically lower",
                }
            ]
        }

    if "SOURCE SENTENCE" in prompt:
        return {
            "discovered_claims": [
                {
                    "type": "conditional",
                    "concept": "measure A",
                    "statement": (
                        "Under condition X, measure A generally increases."
                    ),
                    "parameterisation": "condition X",
                    "source_anchor": "measure A generally increases",
                }
            ]
        }

    if schema == coverage.claim_decomposition_output_schema():
        return {
            "requires_decomposition": False,
            "atomic_claims": [],
        }

    if "CANDIDATE PROPOSITION" in prompt:
        return {
            "represented": False,
            "represented_by": None,
        }

    raise AssertionError(f"Unexpected integrated prompt: {prompt}")


integrated_result = coverage.assess_claim_coverage_two_stage(
    answer_draft=integrated_answer,
    existing_claims=[],
    assessor=integrated_assessor,
)

assert len(integrated_result.discovered_claims) == 2
assert {
    item.claim.statement
    for item in integrated_result.discovered_claims
} == {
    "Under condition X, measure A generally increases.",
    "Under condition X, measure B is typically lower.",
}
assert {
    claim.statement
    for claim in integrated_result.missing_claims
} == {
    "Under condition X, measure A generally increases.",
    "Under condition X, measure B is typically lower.",
}
assert any("ANSWER DRAFT" in prompt for prompt in integrated_calls)
assert any("SOURCE SENTENCE" in prompt for prompt in integrated_calls)

print("PASS: two-stage coverage audits discovery before representation filtering")

print("\n[46] decomposition schema exposes only decision and atomic replacements")

decomposition_schema = coverage.claim_decomposition_output_schema()

assert decomposition_schema["type"] == "object"
assert set(decomposition_schema["properties"]) == {
    "requires_decomposition",
    "atomic_claims",
}
assert set(decomposition_schema["required"]) == {
    "requires_decomposition",
    "atomic_claims",
}
assert decomposition_schema["additionalProperties"] is False

atomic_item = decomposition_schema["properties"]["atomic_claims"]["items"]
assert set(atomic_item["properties"]) == {
    "type",
    "concept",
    "statement",
    "parameterisation",
    "source_anchor",
}
assert atomic_item["additionalProperties"] is False

print("PASS: decomposition schema grants only bounded replacement authority")


print("\n[47] decomposition prompt has a narrow atomicity role")

compound_claim = academic_chat.TechnicalClaim(
    type="comparative",
    concept="posterior interval behaviour",
    statement=(
        "For skewed unimodal posteriors, the endpoints generally differ, "
        "and the minimum-width HDI is typically narrower than the ETI."
    ),
    parameterisation=None,
)
compound_sentence = (
    "However, for skewed unimodal posteriors, the endpoints generally differ, "
    "and the minimum-width HDI is typically narrower than the ETI."
)

decomposition_prompt = coverage.build_claim_decomposition_prompt(
    claim=compound_claim,
    source_sentence=compound_sentence,
)
decomposition_normalized = " ".join(decomposition_prompt.lower().split())

assert compound_sentence in decomposition_prompt
assert compound_claim.statement in decomposition_prompt
assert "independently checkable" in decomposition_normalized
assert "could differ in support or correctness" in decomposition_normalized
assert "do not use outside knowledge" in decomposition_normalized
assert "do not judge whether" in decomposition_normalized
assert "true or false" in decomposition_normalized
assert "do not verify" in decomposition_normalized
assert "do not recover propositions" in decomposition_normalized
assert "omission recovery is handled separately" in decomposition_normalized
assert "condition and the proposition it qualifies" in decomposition_normalized
assert "comparison should remain intact" in decomposition_normalized
assert "generally" in decomposition_normalized
assert "typically" in decomposition_normalized
assert "do not strengthen or weaken" in decomposition_normalized
assert "source_anchor" in decomposition_prompt
assert "do not retain the original compound claim" in decomposition_normalized

print("PASS: decomposition is bounded to atomic replacement, not assessment")

print("\n[48] valid compound claim is replaced by atomic children")

decomposition_answer = (
    "For skewed unimodal posteriors, the endpoints generally differ, "
    "and the minimum-width HDI is typically narrower than the ETI."
)
compound_anchor = decomposition_answer
compound_discovered = coverage.DiscoveredClaim(
    claim=compound_claim,
    source_anchor=compound_anchor,
    source_start=0,
    source_end=len(compound_anchor),
)


def valid_decomposer(*, prompt, schema):
    assert schema == coverage.claim_decomposition_output_schema()
    assert compound_claim.statement in prompt
    assert decomposition_answer in prompt
    return {
        "requires_decomposition": True,
        "atomic_claims": [
            {
                "type": "comparison",
                "concept": "ETI and HDI endpoints",
                "statement": (
                    "For skewed unimodal posteriors, "
                    "the endpoints generally differ."
                ),
                "parameterisation": "skewed unimodal posterior",
                "source_anchor": "the endpoints generally differ",
            },
            {
                "type": "comparison",
                "concept": "ETI and HDI width",
                "statement": (
                    "For skewed unimodal posteriors, the minimum-width "
                    "HDI is typically narrower than the ETI."
                ),
                "parameterisation": "skewed unimodal posterior",
                "source_anchor": (
                    "the minimum-width HDI is typically narrower than the ETI"
                ),
            },
        ],
    }


atomic_result = coverage.decompose_discovered_claims(
    answer_draft=decomposition_answer,
    discovered_claims=[compound_discovered],
    assessor=valid_decomposer,
)

assert len(atomic_result) == 2
assert {
    item.claim.statement
    for item in atomic_result
} == {
    (
        "For skewed unimodal posteriors, "
        "the endpoints generally differ."
    ),
    (
        "For skewed unimodal posteriors, the minimum-width "
        "HDI is typically narrower than the ETI."
    ),
}
assert all(
    decomposition_answer[
        item.source_start:item.source_end
    ] == item.source_anchor
    for item in atomic_result
)

print("PASS: valid compound claim is replaced by atomic propositions")


print("\n[49] already atomic claim is preserved unchanged")


def atomic_decomposer(*, prompt, schema):
    return {
        "requires_decomposition": False,
        "atomic_claims": [],
    }


atomic_input = coverage.DiscoveredClaim(
    claim=academic_chat.TechnicalClaim(
        type="comparison",
        concept="interval width",
        statement="The HDI may be narrower than the ETI.",
        parameterisation=None,
    ),
    source_anchor="The HDI may be narrower than the ETI",
    source_start=0,
    source_end=len("The HDI may be narrower than the ETI"),
)

atomic_preserved = coverage.decompose_discovered_claims(
    answer_draft="The HDI may be narrower than the ETI.",
    discovered_claims=[atomic_input],
    assessor=atomic_decomposer,
)

assert atomic_preserved == [atomic_input]

print("PASS: decomposition does not rewrite an already atomic claim")


print("\n[50] incomplete decomposition cannot replace original claim")


def incomplete_decomposer(*, prompt, schema):
    return {
        "requires_decomposition": True,
        "atomic_claims": [
            {
                "type": "comparison",
                "concept": "ETI and HDI endpoints",
                "statement": (
                    "For skewed unimodal posteriors, "
                    "the endpoints generally differ."
                ),
                "parameterisation": "skewed unimodal posterior",
                "source_anchor": "the endpoints generally differ",
            }
        ],
    }


incomplete_result = coverage.decompose_discovered_claims(
    answer_draft=decomposition_answer,
    discovered_claims=[compound_discovered],
    assessor=incomplete_decomposer,
)

assert incomplete_result == [compound_discovered]

print("PASS: fewer than two valid children cannot erase compound coverage")


print("\n[51] malformed atomic child cannot create false provenance")


def malformed_child_decomposer(*, prompt, schema):
    return {
        "requires_decomposition": True,
        "atomic_claims": [
            {
                "type": "comparison",
                "concept": "ETI and HDI endpoints",
                "statement": (
                    "For skewed unimodal posteriors, "
                    "the endpoints generally differ."
                ),
                "parameterisation": "skewed unimodal posterior",
                "source_anchor": "anchor absent from source sentence",
            },
            {
                "type": "comparison",
                "concept": "ETI and HDI width",
                "statement": (
                    "For skewed unimodal posteriors, the minimum-width "
                    "HDI is typically narrower than the ETI."
                ),
                "parameterisation": "skewed unimodal posterior",
                "source_anchor": (
                    "the minimum-width HDI is typically narrower than the ETI"
                ),
            },
        ],
    }


malformed_child_result = coverage.decompose_discovered_claims(
    answer_draft=decomposition_answer,
    discovered_claims=[compound_discovered],
    assessor=malformed_child_decomposer,
)

assert malformed_child_result == [compound_discovered]

print("PASS: malformed child prevents unsafe compound replacement")


print("\n[51b] decomposition inference failure preserves original claim")


def failing_decomposer(*, prompt, schema):
    raise coverage.ClaimCoverageOutputError(
        "Synthetic decomposition inference failure."
    )


failed_decomposition_result = coverage.decompose_discovered_claims(
    answer_draft=decomposition_answer,
    discovered_claims=[compound_discovered],
    assessor=failing_decomposer,
)

assert failed_decomposition_result == [compound_discovered]

print("PASS: decomposition inference failure cannot erase original claim")


print("\n[52] two-stage coverage decomposes compound claims before representation")

compound_answer = (
    "For skewed unimodal posteriors, the endpoints generally differ, "
    "and the minimum-width HDI is typically narrower than the ETI."
)
compound_representation_candidates = []


def compound_integrated_assessor(*, prompt, schema):
    if "ANSWER DRAFT" in prompt:
        return {
            "discovered_claims": [
                {
                    "type": "comparison",
                    "concept": "ETI and HDI behaviour",
                    "statement": compound_answer,
                    "parameterisation": None,
                    "source_anchor": compound_answer,
                }
            ]
        }

    if "SOURCE SENTENCE" in prompt and "already extracted" in prompt:
        return {
            "discovered_claims": []
        }

    if "requires_decomposition" in str(schema):
        return {
            "requires_decomposition": True,
            "atomic_claims": [
                {
                    "type": "statistical",
                    "concept": "endpoint difference",
                    "statement": (
                        "For skewed unimodal posteriors, "
                        "the endpoints generally differ."
                    ),
                    "parameterisation": None,
                    "source_anchor": "the endpoints generally differ",
                },
                {
                    "type": "statistical",
                    "concept": "interval width comparison",
                    "statement": (
                        "For skewed unimodal posteriors, the minimum-width "
                        "HDI is typically narrower than the ETI."
                    ),
                    "parameterisation": None,
                    "source_anchor": (
                        "the minimum-width HDI is typically narrower than the ETI"
                    ),
                },
            ],
        }

    if "CANDIDATE PROPOSITION" in prompt:
        compound_representation_candidates.append(prompt)
        return {
            "represented": False,
            "represented_by": None,
        }

    raise AssertionError(f"Unexpected compound integration prompt: {prompt}")


compound_integrated_result = coverage.assess_claim_coverage_two_stage(
    answer_draft=compound_answer,
    existing_claims=[],
    assessor=compound_integrated_assessor,
)

compound_statements = {
    item.claim.statement
    for item in compound_integrated_result.discovered_claims
}

assert compound_statements == {
    (
        "For skewed unimodal posteriors, "
        "the endpoints generally differ."
    ),
    (
        "For skewed unimodal posteriors, the minimum-width "
        "HDI is typically narrower than the ETI."
    ),
}

assert len(compound_representation_candidates) == 2
assert all(
    compound_answer not in prompt
    for prompt in compound_representation_candidates
)

assert {
    claim.statement
    for claim in compound_integrated_result.missing_claims
} == compound_statements

print("PASS: representation receives atomic children rather than compound parent")
