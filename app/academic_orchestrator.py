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
import academic_claims
import academic_technical
from academic_tools import AcademicReferenceResult, verify_academic_reference


@dataclass
class RetrievalIdentity:
    """Bibliographic identity permitted to cross into source retrieval."""

    status: str
    doi: str | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "doi": self.doi,
            "reasons": self.reasons,
        }


def resolve_retrieval_identity(
    verification: AcademicReferenceResult,
) -> RetrievalIdentity:
    """Decide whether bibliographic identity is safe for source retrieval."""
    if verification.identity_conflict:
        return RetrievalIdentity(
            status="not_eligible",
            doi=None,
            reasons=[
                "Conflicting bibliographic identities prevent automatic "
                "source retrieval."
            ],
        )

    if verification.crossref_verification.status == "verified":
        for corroboration in (
            verification.doi_corroboration,
            verification.related_corroboration,
        ):
            if (
                corroboration is not None
                and corroboration.status == "corroborated"
                and corroboration.same_doi
                and corroboration.crossref is not None
                and corroboration.openalex is not None
            ):
                crossref_doi = corroboration.crossref.doi.strip().lower()
                openalex_doi = corroboration.openalex.doi.strip().lower()

                if crossref_doi and crossref_doi == openalex_doi:
                    return RetrievalIdentity(
                        status="eligible",
                        doi=crossref_doi,
                        reasons=[
                            "Verified bibliographic metadata and "
                            "cross-database DOI corroboration establish "
                            "a retrieval identity."
                        ],
                    )

    return RetrievalIdentity(
        status="not_eligible",
        doi=None,
        reasons=[
            "No retrieval-eligible bibliographic identity has been established."
        ],
    )


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
class SourceDiscoveryResult:
    """Whether source discovery was attempted for a safe retrieval identity."""

    status: str
    location: academic_claims.SourceLocation | None
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "location": (
                self.location.to_dict()
                if self.location is not None
                else None
            ),
            "reasons": self.reasons,
        }


@dataclass
class SourceClaimResult:
    claim: academic_chat.SourceClaim
    reference: VerifiedReferenceProposal
    retrieval_identity: RetrievalIdentity
    source_discovery: SourceDiscoveryResult
    source_retrieval: academic_claims.RetrievedSource | None = None
    claim_location: academic_claims.ClaimSupportResult | None = None
    claim_assessment: academic_claims.ClaimAssessmentResult | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "reference": self.reference.to_dict(),
            "retrieval_identity": self.retrieval_identity.to_dict(),
            "source_discovery": self.source_discovery.to_dict(),
            "source_retrieval": (
                self.source_retrieval.to_dict()
                if self.source_retrieval is not None
                else None
            ),
            "claim_location": (
                self.claim_location.to_dict()
                if self.claim_location is not None
                else None
            ),
            "claim_assessment": (
                self.claim_assessment.to_dict()
                if self.claim_assessment is not None
                else None
            ),
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
class AcademicReleaseAssessment:
    status: str
    safe_to_present: bool
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "safe_to_present": self.safe_to_present,
            "reasons": self.reasons,
        }


def assess_academic_release(
    technical_claims: list[TechnicalClaimResult],
) -> AcademicReleaseAssessment:
    """Assess whether a technically checked draft may be presented.

    A recognised deterministic technical conflict blocks release.
    Claims outside deterministic verifier coverage remain visible but do not
    by themselves establish that the draft is incorrect.
    """
    statuses = [
        claim.verification.status
        for claim in technical_claims
    ]

    if academic_technical.TECHNICAL_STATUS_CONFLICT in statuses:
        return AcademicReleaseAssessment(
            status="blocked_technical_conflict",
            safe_to_present=False,
            reasons=[
                "At least one structured technical claim conflicts with "
                "deterministic technical verification."
            ],
        )

    if academic_technical.TECHNICAL_STATUS_NOT_VERIFIED in statuses:
        return AcademicReleaseAssessment(
            status="release_allowed_with_unverified_claims",
            safe_to_present=True,
            reasons=[
                "At least one structured technical claim was not technically "
                "verified; absence of deterministic verification is not "
                "treated as a technical conflict."
            ],
        )

    return AcademicReleaseAssessment(
        status="release_allowed",
        safe_to_present=True,
        reasons=[
            "No deterministic technical conflict was identified."
        ],
    )


@dataclass
class AcademicFirstStageResult:
    answer_draft: str
    references: list[VerifiedReferenceProposal]
    source_claims: list[SourceClaimResult]
    technical_claims: list[TechnicalClaimResult]
    release: AcademicReleaseAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_draft": self.answer_draft,
            "references": [
                reference.to_dict()
                for reference in self.references
            ],
            "source_claims": [
                claim.to_dict()
                for claim in self.source_claims
            ],
            "technical_claims": [
                claim.to_dict()
                for claim in self.technical_claims
            ],
            "release": self.release.to_dict(),
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
    source_discoverer: Callable[[str], Any] | None = None,
    source_retriever: Callable[
        [academic_claims.SourceLocation],
        academic_claims.RetrievedSource,
    ] | None = None,
    claim_locator: Callable[
        [academic_claims.RetrievedSource, str],
        academic_claims.ClaimSupportResult,
    ] | None = None,
    claim_assessor: Callable[
        [str, list[academic_claims.ClaimEvidence]],
        academic_claims.ClaimAssessmentResult,
    ] | None = None,
) -> AcademicFirstStageResult:
    """
    Generate a local academic draft, verify its proposed references and
    deterministic technical claims, and resolve source-claim proposals to
    their corresponding verified-reference proposals.

    The full question is passed only to the local draft generator. Reference
    verification receives only the five bibliographic fields defined by the
    AcademicReference contract. Source-claim resolution is local and does not
    establish that a reference supports its associated claim. Technical
    verification receives only each structured TechnicalClaim.
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

    source_claims = []

    for claim in draft.source_claims:
        reference = verified_references[claim.reference_index]
        retrieval_identity = resolve_retrieval_identity(
            reference.verification
        )

        if (
            retrieval_identity.status == "eligible"
            and retrieval_identity.doi is not None
            and source_discoverer is not None
        ):
            try:
                location = source_discoverer(retrieval_identity.doi)
            except RuntimeError:
                source_discovery = SourceDiscoveryResult(
                    status="unavailable",
                    location=None,
                    reasons=["Source discovery service was unavailable."],
                )
            else:
                source_discovery = SourceDiscoveryResult(
                    status="attempted",
                    location=location,
                    reasons=[
                        "Eligible retrieval identity was sent to source discovery."
                    ],
                )
        elif retrieval_identity.status != "eligible":
            source_discovery = SourceDiscoveryResult(
                status="not_attempted",
                location=None,
                reasons=[
                    "Source discovery was not attempted because "
                    "the bibliographic identity was not eligible."
                ],
            )
        else:
            source_discovery = SourceDiscoveryResult(
                status="not_attempted",
                location=None,
                reasons=[
                    "Source discovery was not attempted because "
                    "no source discoverer was supplied."
                ],
            )

        source_retrieval = None

        if (
            source_discovery.status == "attempted"
            and source_discovery.location is not None
            and source_discovery.location.status == "location_found"
            and source_retriever is not None
        ):
            source_retrieval = source_retriever(
                source_discovery.location
            )

        claim_location = None

        if (
            source_retrieval is not None
            and source_retrieval.status == "retrieved"
            and claim_locator is not None
        ):
            claim_location = claim_locator(
                source_retrieval,
                claim.claim,
            )

        claim_assessment = None

        if (
            claim_location is not None
            and claim_location.status == "claim_located"
            and claim_assessor is not None
        ):
            claim_assessment = claim_assessor(
                claim.claim,
                claim_location.evidence,
            )

        source_claims.append(
            SourceClaimResult(
                claim=claim,
                reference=reference,
                retrieval_identity=retrieval_identity,
                source_discovery=source_discovery,
                source_retrieval=source_retrieval,
                claim_location=claim_location,
                claim_assessment=claim_assessment,
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

    release = assess_academic_release(technical_claims)

    return AcademicFirstStageResult(
        answer_draft=draft.answer_draft,
        references=verified_references,
        source_claims=source_claims,
        technical_claims=technical_claims,
        release=release,
    )
