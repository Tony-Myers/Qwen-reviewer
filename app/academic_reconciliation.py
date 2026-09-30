"""
Bounded correction extraction for Academic Chat reconciliation.

This module converts independently established blocking findings into the
minimum application-owned material needed for a later revision attempt.

It does not reassess checker findings or treat absence of
verification/support as a correction requirement. Revision generation is
bounded by the extracted correction material and returns the same AcademicDraft
contract used by first-pass generation.
"""

from dataclasses import dataclass, field
import json
from typing import Any

import academic_chat
import academic_claims
import academic_claim_coverage
import academic_methodology
import academic_orchestrator
import academic_technical
import llm_backend
import reviewer_notes


@dataclass
class TechnicalCorrection:
    claim: academic_chat.TechnicalClaim
    canonical_claim: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "canonical_claim": self.canonical_claim,
        }


@dataclass
class MethodologicalCorrection:
    claim: academic_chat.TechnicalClaim
    passages: list[reviewer_notes.Passage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "passages": [
                {
                    "note": passage.note,
                    "heading": passage.heading,
                    "text": passage.text,
                    "score": passage.score,
                }
                for passage in self.passages
            ],
        }


@dataclass
class ContextualMethodologicalCorrection:
    claim: academic_chat.TechnicalClaim
    source_context: academic_claim_coverage.ClaimSourceContext
    passages: list[reviewer_notes.Passage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "source_sentence": self.source_context.source_sentence,
            "context_excerpt": self.source_context.context_excerpt,
            "passages": [
                {
                    "note": passage.note,
                    "heading": passage.heading,
                    "text": passage.text,
                    "score": passage.score,
                }
                for passage in self.passages
            ],
        }


@dataclass
class SourceCorrection:
    claim: str
    evidence: list[academic_claims.ClaimEvidence]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "evidence": [
                item.to_dict()
                for item in self.evidence
            ],
        }


@dataclass
class AcademicCorrectionSet:
    technical: list[TechnicalCorrection] = field(default_factory=list)
    methodological: list[MethodologicalCorrection] = field(default_factory=list)
    contextual_methodological: list[
        ContextualMethodologicalCorrection
    ] = field(default_factory=list)
    source: list[SourceCorrection] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return whether independent checking established no corrections."""
        return not (
            self.technical
            or self.methodological
            or self.contextual_methodological
            or self.source
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "technical": [
                correction.to_dict()
                for correction in self.technical
            ],
            "methodological": [
                correction.to_dict()
                for correction in self.methodological
            ],
            "contextual_methodological": [
                correction.to_dict()
                for correction in self.contextual_methodological
            ],
            "source": [
                correction.to_dict()
                for correction in self.source
            ],
        }


def extract_academic_corrections(
    *,
    technical_claims: list[academic_orchestrator.TechnicalClaimResult],
    source_claims: list[academic_orchestrator.SourceClaimResult],
    discovered_claim_assessments: (
        list[academic_orchestrator.DiscoveredClaimAssessment] | None
    ) = None,
) -> AcademicCorrectionSet:
    """Extract all independently established blockers from a checked draft."""

    technical: list[TechnicalCorrection] = []
    methodological: list[MethodologicalCorrection] = []
    contextual_methodological: list[
        ContextualMethodologicalCorrection
    ] = []
    source: list[SourceCorrection] = []

    for result in technical_claims:
        if (
            result.verification.status
            == academic_technical.TECHNICAL_STATUS_CONFLICT
        ):
            canonical_claim = result.verification.canonical_claim

            if not canonical_claim:
                raise ValueError(
                    "A deterministic technical conflict requires a canonical "
                    "claim before it can be used for reconciliation."
                )

            technical.append(
                TechnicalCorrection(
                    claim=result.claim,
                    canonical_claim=canonical_claim,
                )
            )

        consistency = result.methodological_consistency

        if (
            consistency is not None
            and consistency.status
            == academic_methodology.METHODOLOGICAL_STATUS_CONFLICT
        ):
            methodological.append(
                MethodologicalCorrection(
                    claim=result.claim,
                    passages=list(consistency.passages),
                )
            )

    for assessment in (discovered_claim_assessments or []):
        consistency = assessment.contextual_methodological_consistency

        if (
            consistency is not None
            and consistency.status
            == academic_methodology.METHODOLOGICAL_STATUS_CONFLICT
        ):
            contextual_methodological.append(
                ContextualMethodologicalCorrection(
                    claim=consistency.claim,
                    source_context=assessment.source_context,
                    passages=list(consistency.passages),
                )
            )

    for result in source_claims:
        assessment = result.claim_assessment

        if (
            assessment is not None
            and assessment.status == "claim_contradicted"
        ):
            source.append(
                SourceCorrection(
                    claim=result.claim.claim,
                    evidence=list(assessment.evidence),
                )
            )

    return AcademicCorrectionSet(
        technical=technical,
        methodological=methodological,
        contextual_methodological=contextual_methodological,
        source=source,
    )


def build_academic_revision_prompt(
    original_draft: academic_chat.AcademicDraft,
    corrections: AcademicCorrectionSet,
) -> str:
    """Build the bounded prompt for revising one checked AcademicDraft.

    The revision model receives the structured draft and only the correction
    material extracted from independently established blockers. It does not
    receive the original user question, release state, or checker audit
    reasons.
    """
    draft_json = json.dumps(
        original_draft.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    corrections_json = json.dumps(
        corrections.to_dict(),
        ensure_ascii=False,
        indent=2,
    )

    return f"""Revise the AcademicDraft below using the supplied corrections.

The supplied corrections have already been established by independent checking.
Do not decide whether they are correct and do not reassess the checker findings.
Address every supplied correction.

Preserve unaffected content, qualifications, references, source claims, and
technical claims where they remain appropriate. Change or remove structured
items when necessary so that the revised answer_draft, references,
source_claims, and technical_claims remain internally consistent with one
another.

Use only the original AcademicDraft and the supplied correction material for
this revision. Do not invent evidence, bibliographic details, verification
results, or methodological guidance.

Return a complete revised AcademicDraft, not a patch, commentary, explanation
of changes, or verification decision. The revised draft will be independently
checked again before it can be presented.

ORIGINAL ACADEMICDRAFT:
{draft_json}

SUPPLIED CORRECTIONS:
{corrections_json}
"""


ACADEMIC_REVISION_SYSTEM_PROMPT = """\
You are the bounded revision component of Academic Chat.

Revise only from the original AcademicDraft and correction material supplied
in the user message. The supplied corrections have already been established by
independent checking; do not reassess whether they are correct.

Return exactly one complete revised AcademicDraft JSON object and no
explanatory text outside it. Do not add verification status, release status,
checker commentary, or other fields outside the AcademicDraft contract.
"""


def revise_academic_draft(
    model: Any,
    tokenizer: Any,
    original_draft: academic_chat.AcademicDraft,
    corrections: AcademicCorrectionSet,
    *,
    max_tokens: int = 2400,
) -> academic_chat.AcademicDraft:
    """Generate one bounded revision as an ordinary AcademicDraft.

    The original user question is deliberately absent from this interface.
    The resulting draft has no inherited verification or release status and
    must be independently assessed before presentation.
    """
    user_content = build_academic_revision_prompt(
        original_draft,
        corrections,
    )

    messages = [
        {
            "role": "system",
            "content": ACADEMIC_REVISION_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    sampler = llm_backend.make_sampler(
        temp=0.1,
        top_p=0.8,
        top_k=20,
        response_format=academic_chat.ACADEMIC_DRAFT_RESPONSE_FORMAT,
    )

    with llm_backend.thinking(False):
        raw = llm_backend.generate(
            model,
            tokenizer,
            messages,
            max_tokens=max_tokens,
            sampler=sampler,
            verbose=False,
        )

    return academic_chat.parse_academic_draft(raw)
