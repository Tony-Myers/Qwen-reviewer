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
    if schema == coverage.claim_discovery_output_schema():
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
