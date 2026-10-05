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


# The semantic model supplies bounded proposition judgements; only the
# application derives the methodological status.
METHODOLOGICAL_COEXISTENCE_VALUES = ("yes", "no", "unclear")
METHODOLOGICAL_ESTABLISHMENT_VALUES = ("yes", "no", "unclear")


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


def methodological_coexistence_output_schema() -> dict[str, Any]:
    """Return the strict schema for proposition-coexistence assessment."""
    return {
        "type": "object",
        "properties": {
            "claim_proposition": {"type": "string", "minLength": 1},
            "guidance_proposition": {"type": "string", "minLength": 1},
            "can_both_be_true": {
                "type": "string",
                "enum": list(METHODOLOGICAL_COEXISTENCE_VALUES),
            },
            "reason": {"type": "string", "minLength": 1},
        },
        "required": [
            "claim_proposition",
            "guidance_proposition",
            "can_both_be_true",
            "reason",
        ],
        "additionalProperties": False,
    }


def methodological_establishment_output_schema() -> dict[str, Any]:
    """Return the strict schema for guidance-establishment assessment."""
    return {
        "type": "object",
        "properties": {
            "claim_proposition": {"type": "string", "minLength": 1},
            "guidance_proposition": {"type": "string", "minLength": 1},
            "guidance_establishes_claim": {
                "type": "string",
                "enum": list(METHODOLOGICAL_ESTABLISHMENT_VALUES),
            },
            "reason": {"type": "string", "minLength": 1},
        },
        "required": [
            "claim_proposition",
            "guidance_proposition",
            "guidance_establishes_claim",
            "reason",
        ],
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


def _methodological_proposition_rules() -> str:
    """Return shared proposition-extraction rules."""
    return """Use only the supplied guidance.
Do not use outside knowledge.
Do not treat retrieval of a passage as evidence that it addresses the claim.

State claim_proposition: the material proposition actually asserted by the
claim, preserving frequency, quantifiers, modality, direction, degree,
conditions and context.

State guidance_proposition: what the supplied guidance actually establishes,
preserving the same distinctions. If it establishes no relevant proposition,
say so explicitly rather than inventing one.

Keep each proposition concise. Do not strengthen or weaken either proposition."""


def _methodological_coexistence_rules() -> str:
    """Return rules for the bounded proposition-coexistence judgement."""
    return _methodological_proposition_rules() + """

Then answer one question only:

Can both material propositions be true at the same time under the same
relevant conditions?

yes
The propositions can coexist.

no
The propositions cannot both be true under the same relevant conditions.
Use no only for an actual incompatibility.

unclear
The supplied text does not establish whether the propositions can coexist.

A weaker proposition does not contradict a stronger proposition merely because
the stronger proposition is not established.

Pay particular attention to modal terms such as necessarily, always, never,
can, may, sometimes and possibly. A universal or necessary proposition cannot
coexist with guidance that establishes a permitted counterexample under the
same relevant conditions.

"Typically X" and "not always/universally X" can both be true. Likewise,
"may X" and "not necessarily X", "often X" and "not always X", and
"can improve X" and "does not guarantee improvement" are not automatically
incompatible.

A warning that an inference is not established does not by itself establish
the contrary substantive proposition.

Do not decide whether the guidance supports the claim.

OUTPUT DISCIPLINE
The reason must be one concise sentence of no more than 30 words.
Do not show deliberation, self-correction, or reconsideration.

Return only claim_proposition, guidance_proposition, can_both_be_true, and
reason."""


def _methodological_establishment_rules() -> str:
    """Return rules for the bounded guidance-establishment judgement."""
    return _methodological_proposition_rules() + """

Then answer one question only:

Does the supplied guidance establish the claim's complete material
proposition?

yes
The guidance establishes the complete claim, including its important
quantifiers, modality, frequency, direction, degree, conditions and context.

no
The guidance does not establish the complete claim.

unclear
It cannot be determined from the supplied guidance whether the complete claim
is established.

A weaker proposition does not establish a stronger proposition.
Compatibility alone is not support.
Guidance about a different property does not establish the claim merely
because both concern the same topic.

Do not decide whether the propositions conflict.

The reason must be one concise sentence of no more than 30 words.

Return only claim_proposition, guidance_proposition,
guidance_establishes_claim, and reason."""


def _build_methodological_prompt(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
    *,
    rules: str,
    task: str,
) -> str:
    """Build one bounded methodological proposition-assessment prompt."""
    claim_block = _format_methodological_claim(claim)
    guidance_block = _format_methodological_guidance(passages)

    return f"""{task}

GENERATED CLAIM
{claim_block}

CURATED METHODOLOGICAL GUIDANCE
{guidance_block}

{rules}
"""


def build_methodological_coexistence_prompt(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build a guidance-bounded proposition-coexistence prompt."""
    return _build_methodological_prompt(
        claim,
        passages,
        rules=_methodological_coexistence_rules(),
        task=(
            "Assess logical coexistence between the generated methodological "
            "claim and the supplied curated methodological guidance."
        ),
    )


def build_methodological_establishment_prompt(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build a guidance-bounded claim-establishment prompt."""
    return _build_methodological_prompt(
        claim,
        passages,
        rules=_methodological_establishment_rules(),
        task=(
            "Assess whether the supplied curated methodological guidance "
            "establishes the generated methodological claim."
        ),
    )


def _validate_methodological_output(
    assessor_output: Any,
    *,
    judgement_field: str,
    allowed_values: tuple[str, ...],
) -> tuple[str, str]:
    """Validate one bounded semantic judgement and return value and reason."""
    if not isinstance(assessor_output, dict):
        raise MethodologicalAssessmentOutputError(
            "Methodological assessor output must be an object."
        )

    expected_fields = {
        "claim_proposition",
        "guidance_proposition",
        judgement_field,
        "reason",
    }
    if set(assessor_output) != expected_fields:
        raise MethodologicalAssessmentOutputError(
            "Methodological assessor output contains unexpected or missing "
            "fields."
        )

    for field in ("claim_proposition", "guidance_proposition"):
        value = assessor_output[field]
        if not isinstance(value, str) or not value.strip():
            raise MethodologicalAssessmentOutputError(
                f"Methodological {field} must be non-empty text."
            )

    judgement = assessor_output[judgement_field]
    if (
        not isinstance(judgement, str)
        or judgement not in allowed_values
    ):
        raise MethodologicalAssessmentOutputError(
            f"Methodological {judgement_field} contains an invalid value."
        )

    reason = assessor_output["reason"]
    if not isinstance(reason, str) or not reason.strip():
        raise MethodologicalAssessmentOutputError(
            "Methodological reason must be non-empty text."
        )
    if len(reason.split()) > 30:
        raise MethodologicalAssessmentOutputError(
            "Methodological reason must contain no more than 30 words."
        )

    return judgement, reason.strip()


def _derive_methodological_status(
    coexistence: str,
    establishment: str,
) -> str:
    """Derive application-owned status from bounded semantic judgements."""
    if coexistence == "no":
        return METHODOLOGICAL_STATUS_CONFLICT
    if coexistence == "yes" and establishment == "yes":
        return METHODOLOGICAL_STATUS_CONSISTENT
    return METHODOLOGICAL_STATUS_NOT_ESTABLISHED


def build_methodological_consistency(
    claim: academic_chat.TechnicalClaim,
    passages: list[reviewer_notes.Passage],
    coexistence_output: Any,
    establishment_output: Any,
) -> MethodologicalConsistencyResult:
    """Validate bounded judgements and attach application-owned provenance."""
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

    coexistence, coexistence_reason = _validate_methodological_output(
        coexistence_output,
        judgement_field="can_both_be_true",
        allowed_values=METHODOLOGICAL_COEXISTENCE_VALUES,
    )
    establishment, establishment_reason = _validate_methodological_output(
        establishment_output,
        judgement_field="guidance_establishes_claim",
        allowed_values=METHODOLOGICAL_ESTABLISHMENT_VALUES,
    )

    return MethodologicalConsistencyResult(
        status=_derive_methodological_status(coexistence, establishment),
        claim=claim,
        passages=list(passages),
        reasons=[coexistence_reason, establishment_reason],
    )


def _build_contextual_methodological_prompt(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
    rules: str,
    task: str,
) -> str:
    """Build one occurrence-aware bounded methodological prompt."""
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

    return f"""{task}

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


def build_contextual_methodological_coexistence_prompt(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build an occurrence-aware proposition-coexistence prompt."""
    return _build_contextual_methodological_prompt(
        claim=claim,
        source_context=source_context,
        passages=passages,
        rules=_methodological_coexistence_rules(),
        task=(
            "Assess logical coexistence between the generated methodological "
            "claim, interpreted at its verified answer occurrence, and the "
            "supplied curated methodological guidance."
        ),
    )


def build_contextual_methodological_establishment_prompt(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
) -> str:
    """Build an occurrence-aware guidance-establishment prompt."""
    return _build_contextual_methodological_prompt(
        claim=claim,
        source_context=source_context,
        passages=passages,
        rules=_methodological_establishment_rules(),
        task=(
            "Assess whether the supplied curated methodological guidance "
            "establishes the generated methodological claim, interpreted "
            "at its verified answer occurrence."
        ),
    )


def build_contextual_methodological_consistency(
    *,
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
    passages: list[reviewer_notes.Passage],
    coexistence_output: Any,
    establishment_output: Any,
) -> ContextualMethodologicalConsistencyResult:
    """Validate contextual judgements and attach application-owned provenance."""
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
        coexistence_output=coexistence_output,
        establishment_output=establishment_output,
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
    """Assess one verified claim occurrence through two bounded judgements."""
    coexistence_prompt = build_contextual_methodological_coexistence_prompt(
        claim=claim,
        source_context=source_context,
        passages=passages,
    )
    establishment_prompt = build_contextual_methodological_establishment_prompt(
        claim=claim,
        source_context=source_context,
        passages=passages,
    )

    try:
        coexistence_output = assessor(
            prompt=coexistence_prompt,
            schema=methodological_coexistence_output_schema(),
        )
        _validate_methodological_output(
            coexistence_output,
            judgement_field="can_both_be_true",
            allowed_values=METHODOLOGICAL_COEXISTENCE_VALUES,
        )
        establishment_output = assessor(
            prompt=establishment_prompt,
            schema=methodological_establishment_output_schema(),
        )
        return build_contextual_methodological_consistency(
            claim=claim,
            source_context=source_context,
            passages=passages,
            coexistence_output=coexistence_output,
            establishment_output=establishment_output,
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
    """Assess one claim through independent bounded semantic judgements."""
    coexistence_prompt = build_methodological_coexistence_prompt(
        claim=claim,
        passages=passages,
    )
    establishment_prompt = build_methodological_establishment_prompt(
        claim=claim,
        passages=passages,
    )

    try:
        coexistence_output = assessor(
            prompt=coexistence_prompt,
            schema=methodological_coexistence_output_schema(),
        )
        _validate_methodological_output(
            coexistence_output,
            judgement_field="can_both_be_true",
            allowed_values=METHODOLOGICAL_COEXISTENCE_VALUES,
        )
        establishment_output = assessor(
            prompt=establishment_prompt,
            schema=methodological_establishment_output_schema(),
        )
        return build_methodological_consistency(
            claim=claim,
            passages=passages,
            coexistence_output=coexistence_output,
            establishment_output=establishment_output,
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
