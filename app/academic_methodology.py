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
import sys
from typing import Any

import academic_chat
import academic_claim_coverage
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


class MethodologicalAssessmentOutputError(ValueError):
    """Raised when methodology-assessor output violates its contract."""


# Recorded as the reason when the assessor's output for a claim could not be
# used. The claim is then treated as not established, like any other claim the
# guidance does not settle, so one unusable judgement cannot withhold an
# answer; the underlying error is kept in assessment_error for diagnostics.
METHODOLOGICAL_ASSESSMENT_NOT_COMPLETED_REASON = (
    "The methodological check could not be completed for this claim."
)


@dataclass
class MethodologicalConsistencyResult:
    """Auditable assessment of one claim against retrieved local guidance."""

    status: str
    claim: academic_chat.TechnicalClaim
    passages: list[reviewer_notes.Passage]
    reasons: list[str]
    assessment_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = {
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
        if self.assessment_error:
            out["assessment_error"] = self.assessment_error
        return out


@dataclass
class ContextualMethodologicalConsistencyResult:
    """Occurrence-level assessment against retrieved methodological guidance."""

    status: str
    claim: academic_chat.TechnicalClaim
    source_context: academic_claim_coverage.ClaimSourceContext
    passages: list[reviewer_notes.Passage]
    reasons: list[str]
    assessment_error: str = ""


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


def _format_methodological_claim(
    claim: academic_chat.TechnicalClaim,
) -> str:
    """Format one application-owned technical claim for semantic assessment."""
    if not isinstance(claim, academic_chat.TechnicalClaim):
        raise TypeError(
            "Methodological consistency requires a TechnicalClaim."
        )

    parameterisation = (
        claim.parameterisation
        if claim.parameterisation is not None
        else "not specified"
    )

    return "\n".join(
        [
            f"statement: {claim.statement}",
            f"parameterisation: {parameterisation}",
        ]
    )


def _format_methodological_guidance(
    passages: list[reviewer_notes.Passage],
) -> str:
    """Format application-owned reviewer-note passages for assessment."""
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
                    "text:",
                    passage.text,
                ]
            )
        )

    return "\n".join("\n" + block for block in guidance_blocks)


def _methodological_consistency_rules() -> str:
    """Return the shared methodological judgement and output rules."""
    return """RULES
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

A caution that a proposition is not necessarily, universally, or automatically
true does not by itself conflict with a claim that it may, sometimes, often, or
under some conditions be true. Conversely, guidance that something may or
sometimes occurs does not establish that it generally, necessarily, or always
occurs. Treat differences in frequency, modality, and quantifiers as material.

Distinguish a warning about inference from a contrary substantive proposition.
Guidance saying that something "should not be assumed", "cannot be inferred",
"does not necessarily follow", or is "not established" does not by itself
establish that the proposition is false or generally false. Such guidance does
not conflict with a claim that the proposition may, sometimes, often, or
typically occur unless the guidance separately establishes an incompatible
proposition at that frequency or strength.

Additional compatible detail in the guidance does not prevent consistency when
the guidance still directly establishes the claim's complete material
proposition. For example, guidance that establishes that X can improve Y and
also explains how or why it can do so directly supports the claim that X can
improve Y. Treat an added mechanism, explanation, example, or compatible
detail as material only when it restricts, qualifies, or changes the
proposition asserted by the claim.

A stronger claim is not established merely because the guidance supports a
weaker version; unsupported strengthening is not by itself a methodological
conflict. In that situation use methodological_consistency_not_established
unless the supplied guidance also establishes an incompatible proposition.
methodological_conflict requires the guidance to establish an incompatible
proposition about the same relevant concept, conditions, and context.

Treat omitted conditions in the same way. Omitting a condition from a claim
does not by itself establish conflict. An unconditional or more general claim
is not established by guidance that supports the proposition only under a
condition. Use methodological_conflict only if the supplied guidance establishes
that the claim is incompatible when the relevant condition is absent.

OUTPUT DISCIPLINE
Decide the status before writing the reason.
The reason must be one concise sentence of no more than 30 words.
The reason must be consistent with the selected status.
Do not show deliberation, self-correction, or reconsideration in the reason.

Return only the required judgement fields: status and reason.
Do not return the claim, guidance, note names, headings, retrieval scores, or
any other provenance field."""


def build_methodological_consistency_prompt(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build a guidance-bounded methodological-consistency prompt."""
    claim_block = _format_methodological_claim(claim)
    guidance_block = _format_methodological_guidance(passages)
    rules = _methodological_consistency_rules()

    return f"""Assess whether the generated methodological claim is consistent
with the supplied curated methodological guidance.

GENERATED CLAIM
{claim_block}

CURATED METHODOLOGICAL GUIDANCE
{guidance_block}

{rules}
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
        raise MethodologicalAssessmentOutputError(
            "Methodological consistency assessor output must be an object."
        )

    expected_fields = {"status", "reason"}
    if set(assessor_output) != expected_fields:
        raise MethodologicalAssessmentOutputError(
            "Methodological consistency assessor output must contain exactly "
            "'status' and 'reason'."
        )

    status = assessor_output["status"]
    reason = assessor_output["reason"]

    if (
        not isinstance(status, str)
        or status not in METHODOLOGICAL_STATUSES
    ):
        raise MethodologicalAssessmentOutputError(
            "Methodological consistency assessor output contains an invalid "
            "status."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise MethodologicalAssessmentOutputError(
            "Methodological consistency reason must be non-empty text."
        )

    if len(reason.split()) > 30:
        raise MethodologicalAssessmentOutputError(
            "Methodological consistency reason must contain no more than "
            "30 words."
        )

    return MethodologicalConsistencyResult(
        status=status,
        claim=claim,
        passages=list(passages),
        reasons=[reason.strip()],
    )


def build_contextual_methodological_consistency_prompt(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build an occurrence-aware methodological-consistency prompt."""
    if not isinstance(
        source_context,
        academic_claim_coverage.ClaimSourceContext,
    ):
        raise TypeError(
            "Contextual methodological consistency requires "
            "a ClaimSourceContext."
        )

    claim_block = _format_methodological_claim(claim)
    guidance_block = _format_methodological_guidance(passages)
    rules = _methodological_consistency_rules()

    return f"""Assess whether the generated methodological claim, interpreted
at its verified answer occurrence, is consistent with the supplied curated
methodological guidance.

GENERATED CLAIM
{claim_block}

VERIFIED SOURCE SENTENCE
{source_context.source_sentence}

BOUNDED ANSWER CONTEXT
{source_context.context_excerpt}

CONTEXT AUTHORITY
Use the verified answer context only to interpret restrictions that govern
this occurrence of the generated claim.
The answer context is not methodological guidance and cannot establish
methodological consistency or conflict.
Only the supplied curated methodological guidance may establish methodological
consistency or conflict.
Do not treat the answer context as changing the stored claim.
Do not rewrite, repair, strengthen, or weaken the generated claim.

CURATED METHODOLOGICAL GUIDANCE
{guidance_block}

{rules}
"""



def build_contextual_methodological_consistency(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
    assessor_output: Any,
) -> ContextualMethodologicalConsistencyResult:
    """Validate a contextual judgement and attach application-owned provenance."""
    if not isinstance(
        source_context,
        academic_claim_coverage.ClaimSourceContext,
    ):
        raise TypeError(
            "Contextual methodological consistency requires "
            "a ClaimSourceContext."
        )

    validated = build_methodological_consistency(
        claim=claim,
        passages=passages,
        assessor_output=assessor_output,
    )

    return ContextualMethodologicalConsistencyResult(
        status=validated.status,
        claim=claim,
        source_context=source_context,
        passages=list(passages),
        reasons=list(validated.reasons),
    )


def assess_contextual_methodological_consistency(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
    assessor,
) -> ContextualMethodologicalConsistencyResult:
    """Assess one verified claim occurrence against local guidance."""
    prompt = build_contextual_methodological_consistency_prompt(
        claim=claim,
        source_context=source_context,
        passages=passages,
    )
    schema = methodological_consistency_output_schema()

    try:
        assessor_output = assessor(
            prompt=prompt,
            schema=schema,
        )
        return build_contextual_methodological_consistency(
            claim=claim,
            source_context=source_context,
            passages=passages,
            assessor_output=assessor_output,
        )
    except ValueError as exc:
        error = _assessment_not_completed(claim, passages, exc)
        return ContextualMethodologicalConsistencyResult(
            status=METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            claim=claim,
            source_context=source_context,
            passages=list(passages),
            reasons=[METHODOLOGICAL_ASSESSMENT_NOT_COMPLETED_REASON],
            assessment_error=error,
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

    try:
        assessor_output = assessor(
            prompt=prompt,
            schema=schema,
        )
        return build_methodological_consistency(
            claim=claim,
            passages=passages,
            assessor_output=assessor_output,
        )
    except ValueError as exc:
        error = _assessment_not_completed(claim, passages, exc)
        return MethodologicalConsistencyResult(
            status=METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            claim=claim,
            passages=list(passages),
            reasons=[METHODOLOGICAL_ASSESSMENT_NOT_COMPLETED_REASON],
            assessment_error=error,
        )


def _assessment_not_completed(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
    exc: ValueError,
) -> str:
    """Decide whether a failed assessment degrades, and log it if so.

    Only unusable model output degrades to "not established": a contract
    violation (MethodologicalAssessmentOutputError) or output the assessor
    could not decode, which it reports as a ValueError subclass. A failure
    in application-owned inputs -- no retrieved passages, a non-claim --
    is a programming error and is raised as before. Backend failures are
    RuntimeErrors and are not caught here at all.
    """
    if not isinstance(claim, academic_chat.TechnicalClaim) or not (
        isinstance(passages, list)
        and passages
        and all(isinstance(p, reviewer_notes.Passage) for p in passages)
    ):
        raise exc

    error = f"{type(exc).__name__}: {exc}"
    print(
        "[methodology] check not completed for claim "
        f"{claim.statement[:100]!r}: {error}",
        file=sys.stderr,
        flush=True,
    )
    return error
