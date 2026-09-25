"""
Methodological-consistency assessment for Academic Chat.

This module assesses whether a structured technical claim is consistent with
curated local methodological guidance retrieved from reviewer notes.

Reviewer notes are local guidance, not external scholarly evidence and not
deterministic technical verification. Agreement with the notes therefore does
not establish that a claim is independently verified.

Model output used for semantic assessment remains untrusted. This module owns
the assessment contract, prompt construction, validation, and reviewer-note
provenance; model invocation is injected separately.
"""

from dataclasses import dataclass
from typing import Any

import academic_chat
import reviewer_notes


METHODOLOGICAL_STATUS_CONSISTENT = "methodologically_consistent"
METHODOLOGICAL_STATUS_CONFLICT = "methodological_conflict"
METHODOLOGICAL_STATUS_NOT_ESTABLISHED = (
    "methodological_consistency_not_established"
)

METHODOLOGICAL_STATUSES = (
    METHODOLOGICAL_STATUS_CONSISTENT,
    METHODOLOGICAL_STATUS_CONFLICT,
    METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
)


@dataclass
class MethodologicalConsistencyResult:
    """Auditable assessment of one claim against retrieved local guidance."""

    status: str
    claim: academic_chat.TechnicalClaim
    passages: list[reviewer_notes.Passage]
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "claim": self.claim.to_dict(),
            "passages": [
                {
                    "note": passage.note,
                    "heading": passage.heading,
                    "score": passage.score,
                }
                for passage in self.passages
            ],
            "reasons": list(self.reasons),
        }


def methodological_consistency_output_schema() -> dict[str, Any]:
    """Return the strict structured-output schema for consistency assessment."""
    return {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": list(METHODOLOGICAL_STATUSES),
            },
            "reason": {
                "type": "string",
                "minLength": 1,
            },
        },
        "required": ["status", "reason"],
        "additionalProperties": False,
    }


def build_methodological_consistency_prompt(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build a guidance-bounded methodological-consistency prompt."""
    if not isinstance(claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Methodological consistency requires a TechnicalClaim."
        )

    if (
        not isinstance(passages, list)
        or not passages
        or not all(
            isinstance(passage, reviewer_notes.Passage)
            for passage in passages
        )
    ):
        raise ValueError(
            "Methodological consistency requires retrieved reviewer-note "
            "passages."
        )

    guidance_blocks = []

    for index, passage in enumerate(passages, start=1):
        guidance_blocks.append(
            "\n".join(
                [
                    f"GUIDANCE {index}",
                    f"note: {passage.note}",
                    f"heading: {passage.heading}",
                    "text:",
                    passage.text,
                ]
            )
        )

    parameterisation = (
        claim.parameterisation
        if claim.parameterisation is not None
        else "not specified"
    )

    return f"""Assess whether the generated methodological claim is consistent
with the supplied curated methodological guidance.

GENERATED CLAIM
type: {claim.type}
concept: {claim.concept}
statement: {claim.statement}
parameterisation: {parameterisation}

CURATED METHODOLOGICAL GUIDANCE
{chr(10).join(chr(10) + block for block in guidance_blocks)}

RULES
Use only the supplied guidance when judging the claim.
Do not use outside knowledge.
Do not treat retrieval of a passage as evidence that it addresses the claim.
Assess whether the guidance addresses the same methodological proposition,
including important qualifiers, conditions, direction, and context.

Use exactly one of these statuses:

methodologically_consistent
The supplied guidance directly addresses the same material proposition and is
compatible with the claim.

methodological_conflict
The supplied guidance clearly establishes a materially incompatible
proposition about the same relevant concept and context.

methodological_consistency_not_established
The supplied guidance does not address the proposition sufficiently to
establish either consistency or conflict.

Absence of a warning or contrary statement is not evidence of consistency.
A related passage is not necessarily relevant to the proposition being
assessed. Use methodological_conflict only when the supplied guidance provides
clear contrary guidance about the same relevant proposition and context.

OUTPUT DISCIPLINE
Decide the status before writing the reason.
The reason must be one concise sentence of no more than 30 words.
The reason must be consistent with the selected status.
Do not show deliberation, self-correction, or reconsideration in the reason.

Return only the required judgement fields: status and reason.
Do not return the claim, guidance, note names, headings, retrieval scores, or
any other provenance field.
"""


def build_methodological_consistency(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
    assessor_output: Any,
) -> MethodologicalConsistencyResult:
    """Validate an assessor judgement and attach application-owned provenance."""
    if not isinstance(claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Methodological consistency requires a TechnicalClaim."
        )

    if (
        not isinstance(passages, list)
        or not passages
        or not all(
            isinstance(passage, reviewer_notes.Passage)
            for passage in passages
        )
    ):
        raise ValueError(
            "Methodological consistency requires retrieved reviewer-note "
            "passages."
        )

    if not isinstance(assessor_output, dict):
        raise ValueError(
            "Methodological consistency assessor output must be an object."
        )

    expected_fields = {"status", "reason"}
    if set(assessor_output) != expected_fields:
        raise ValueError(
            "Methodological consistency assessor output must contain exactly "
            "'status' and 'reason'."
        )

    status = assessor_output["status"]
    reason = assessor_output["reason"]

    if (
        not isinstance(status, str)
        or status not in METHODOLOGICAL_STATUSES
    ):
        raise ValueError(
            "Methodological consistency assessor output contains an invalid "
            "status."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "Methodological consistency reason must be non-empty text."
        )

    if len(reason.split()) > 30:
        raise ValueError(
            "Methodological consistency reason must contain no more than "
            "30 words."
        )

    return MethodologicalConsistencyResult(
        status=status,
        claim=claim,
        passages=list(passages),
        reasons=[reason.strip()],
    )


def assess_methodological_consistency(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
    assessor,
) -> MethodologicalConsistencyResult:
    """Assess a claim against local guidance through an injected assessor."""
    prompt = build_methodological_consistency_prompt(
        claim=claim,
        passages=passages,
    )
    schema = methodological_consistency_output_schema()

    assessor_output = assessor(
        prompt=prompt,
        schema=schema,
    )

    return build_methodological_consistency(
        claim=claim,
        passages=passages,
        assessor_output=assessor_output,
    )
