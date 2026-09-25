"""
Bounded correction extraction for Academic Chat reconciliation.

This module converts independently established blocking findings into the
minimum application-owned material needed for a later revision attempt.

It does not generate revised text, reassess checker findings, or treat absence
of verification/support as a correction requirement.
"""

from dataclasses import dataclass
import json
from typing import Any

import academic_chat
import academic_claims
import academic_methodology
import academic_orchestrator
import academic_technical
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
    technical: list[TechnicalCorrection]
    methodological: list[MethodologicalCorrection]
    source: list[SourceCorrection]

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
            "source": [
                correction.to_dict()
                for correction in self.source
            ],
        }


def extract_academic_corrections(
    *,
    technical_claims: list[academic_orchestrator.TechnicalClaimResult],
    source_claims: list[academic_orchestrator.SourceClaimResult],
) -> AcademicCorrectionSet:
    """Extract all independently established blockers from a checked draft."""

    technical: list[TechnicalCorrection] = []
    methodological: list[MethodologicalCorrection] = []
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
