"""
First-stage orchestration for Academic Chat.

This module joins the local structured Academic Chat draft to bibliographic
and deterministic technical verification while preserving the boundary
between:

- model-proposed content,
- bibliographic verification,
- deterministic technical verification, and
- claim verification.

The complete user question is available only to the local draft-generation
stage. External reference verification receives bibliographic metadata only.
Deterministic technical verification receives only structured technical
claims and performs no external network access.
"""

from dataclasses import dataclass
from typing import Any, Callable

import academic_chat
import academic_technical
from academic_tools import AcademicReferenceResult, verify_academic_reference


@dataclass
class VerifiedReferenceProposal:
    proposed_reference: academic_chat.AcademicReference
    verification: AcademicReferenceResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed_reference": self.proposed_reference.to_dict(),
            "verification": self.verification.to_dict(),
        }


@dataclass
class TechnicalClaimResult:
    claim: academic_chat.TechnicalClaim
    verification: academic_technical.TechnicalVerification

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "verification": self.verification.to_dict(),
        }


@dataclass
class AcademicFirstStageResult:
    answer_draft: str
    references: list[VerifiedReferenceProposal]
    technical_claims: list[TechnicalClaimResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_draft": self.answer_draft,
            "references": [
                reference.to_dict()
                for reference in self.references
            ],
            "technical_claims": [
                claim.to_dict()
                for claim in self.technical_claims
            ],
        }


def run_academic_first_stage(
    model: Any,
    tokenizer: Any,
    question: str,
    *,
    draft_generator: Callable[..., academic_chat.AcademicDraft] | None = None,
    reference_verifier: Callable[..., AcademicReferenceResult] | None = None,
    technical_verifier: Callable[
        [academic_chat.TechnicalClaim],
        academic_technical.TechnicalVerification,
    ] | None = None,
) -> AcademicFirstStageResult:
    """
    Generate a local academic draft and verify its proposed references and
    supported deterministic technical claims.

    The full question is passed only to the local draft generator. Reference
    verification receives only the five bibliographic fields defined by the
    AcademicReference contract. Technical verification receives only each
    structured TechnicalClaim.
    """
    if draft_generator is None:
        draft_generator = academic_chat.generate_academic_draft

    if reference_verifier is None:
        reference_verifier = verify_academic_reference

    if technical_verifier is None:
        technical_verifier = academic_technical.verify_technical_claim

    draft = draft_generator(
        model,
        tokenizer,
        question,
    )

    verified_references = []

    for reference in draft.references:
        verification = reference_verifier(
            title=reference.title,
            author=reference.author,
            year=reference.year,
            venue=reference.venue,
            doi=reference.doi,
        )

        verified_references.append(
            VerifiedReferenceProposal(
                proposed_reference=reference,
                verification=verification,
            )
        )

    technical_claims = []

    for claim in draft.technical_claims:
        verification = technical_verifier(claim)

        technical_claims.append(
            TechnicalClaimResult(
                claim=claim,
                verification=verification,
            )
        )

    return AcademicFirstStageResult(
        answer_draft=draft.answer_draft,
        references=verified_references,
        technical_claims=technical_claims,
    )
