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
import threading
from typing import Any, Callable

import academic_chat
import academic_claim_coverage
import academic_claims
import academic_methodology
import academic_technical
import reviewer_notes
from academic_tools import AcademicReferenceResult, verify_academic_reference


_methodological_notes_index = None
_methodological_notes_index_lock = threading.Lock()


@dataclass
class LocalGuidanceResult:
    """Curated local methodological guidance supplied to draft generation."""

    passages: list[reviewer_notes.Passage]

    @property
    def prompt_text(self) -> str:
        return "\n\n".join(
            f"{passage.note} - {passage.heading}\n{passage.text}"
            for passage in self.passages
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": "reviewer_notes",
            "passages": [
                {
                    "note": passage.note,
                    "heading": passage.heading,
                    "score": passage.score,
                }
                for passage in self.passages
            ],
        }


def retrieve_methodological_context(
    question: str,
    k: int = 3,
) -> LocalGuidanceResult:
    """Retrieve curated local methodological guidance for Academic Chat."""
    global _methodological_notes_index

    with _methodological_notes_index_lock:
        if _methodological_notes_index is None:
            _methodological_notes_index = reviewer_notes.NotesIndex()
        index = _methodological_notes_index

    anchors = index.search(question, k=k)
    passages = reviewer_notes.expand_section_siblings(
        anchors,
        index.passages,
    )

    return LocalGuidanceResult(passages=passages)


def _technical_claim_proposition_key(
    claim: academic_chat.TechnicalClaim,
) -> tuple[str, str | None]:
    """Return substantive identity for proposition-level technical checking.

    Generated type and concept labels are descriptive metadata rather than
    part of the proposition assessed by deterministic or methodological
    checking. Exact statement and parameterisation identity is deliberately
    required here; semantic equivalence remains the responsibility of the
    bounded representation assessment.
    """
    return (
        claim.statement.strip(),
        (
            claim.parameterisation.strip()
            if isinstance(claim.parameterisation, str)
            else claim.parameterisation
        ),
    )


def _technical_claim_methodological_query(
    claim: academic_chat.TechnicalClaim,
) -> str:
    """Build a deterministic local-guidance query from a technical claim."""
    parts = [
        claim.statement,
        claim.parameterisation,
    ]
    return "\n".join(
        part.strip()
        for part in parts
        if isinstance(part, str) and part.strip()
    )


def _contextual_claim_methodological_query(
    claim: academic_chat.TechnicalClaim,
    source_context: academic_claim_coverage.ClaimSourceContext,
) -> str:
    """Build a deterministic guidance query from a claim and verified context."""
    claim_query = _technical_claim_methodological_query(claim)

    parts = [
        "TECHNICAL CLAIM",
        claim_query,
        "VERIFIED SOURCE SENTENCE",
        source_context.source_sentence,
        "BOUNDED ANSWER CONTEXT",
        source_context.context_excerpt,
    ]

    return "\n".join(
        part.strip()
        for part in parts
        if isinstance(part, str) and part.strip()
    )


def _normalise_retrieval_doi(doi: str | None) -> str | None:
    """Normalise a DOI for retrieval-identity continuity checks."""
    if doi is None:
        return None

    cleaned = doi.strip()
    for prefix in (
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    return cleaned.lower() or None


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

    if verification.corroboration_status != "complete":
        return RetrievalIdentity(
            status="not_eligible",
            doi=None,
            reasons=[
                "Incomplete cross-database corroboration prevents automatic "
                "source retrieval."
            ],
        )

    if verification.crossref_verification.status == "verified":
        verified_candidate = verification.crossref_verification.candidate
        verified_doi = (
            verified_candidate.doi.strip().lower()
            if verified_candidate is not None and verified_candidate.doi
            else None
        )

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

                if (
                    verified_doi
                    and crossref_doi == verified_doi
                    and openalex_doi == verified_doi
                ):
                    return RetrievalIdentity(
                        status="eligible",
                        doi=verified_doi,
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
    methodological_consistency: (
        academic_methodology.MethodologicalConsistencyResult | None
    ) = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.to_dict(),
            "verification": self.verification.to_dict(),
            "methodological_consistency": (
                self.methodological_consistency.to_dict()
                if self.methodological_consistency is not None
                else None
            ),
        }


@dataclass
class DiscoveredClaimAssessment:
    """Occurrence-level evidence retained for an independently discovered claim."""

    discovered_claim: academic_claim_coverage.DiscoveredClaim
    source_context: academic_claim_coverage.ClaimSourceContext
    material_restriction: (
        academic_claim_coverage.MaterialRestrictionAssessment | None
    ) = None
    contextual_methodological_consistency: (
        academic_methodology.ContextualMethodologicalConsistencyResult | None
    ) = None

    def to_dict(self) -> dict[str, Any]:
        """Expose a bounded public view of occurrence-level context assessment."""
        methodology = self.contextual_methodological_consistency

        return {
            "claim_statement": self.discovered_claim.claim.statement,
            "source_sentence": self.source_context.source_sentence,
            "context_excerpt": self.source_context.context_excerpt,
            "material_restriction_omitted": (
                self.material_restriction.material_restriction_omitted
                if self.material_restriction is not None
                else None
            ),
            "contextual_methodological_consistency": (
                {
                    "status": methodology.status,
                    "reasons": list(methodology.reasons),
                    "passages": [
                        {
                            "note": passage.note,
                            "heading": passage.heading,
                            "score": passage.score,
                        }
                        for passage in methodology.passages
                    ],
                }
                if methodology is not None
                else None
            ),
        }


def standalone_methodology_is_contextually_superseded(
    claim: academic_chat.TechnicalClaim,
    discovered_claim_assessments: (
        list[DiscoveredClaimAssessment] | None
    ),
) -> bool:
    """Return whether contextual checking supersedes standalone methodology.

    Supersession is deliberately narrow. At least one occurrence of the same
    structured claim must be known to omit a material restriction, and every
    such occurrence must have completed contextual methodological assessment.

    This prevents one assessed occurrence of a deduplicated proposition from
    neutralising a standalone conflict while another materially restricted
    occurrence remains contextually unassessed.
    """
    restricted_occurrences = [
        assessment
        for assessment in (discovered_claim_assessments or [])
        if (
            assessment.discovered_claim.claim == claim
            and assessment.material_restriction is not None
            and assessment.material_restriction.material_restriction_omitted
        )
    ]

    return bool(restricted_occurrences) and all(
        assessment.contextual_methodological_consistency is not None
        for assessment in restricted_occurrences
    )


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
    source_claims: list[SourceClaimResult] | None = None,
    discovered_claim_assessments: (
        list[DiscoveredClaimAssessment] | None
    ) = None,
    claim_coverage: (
        academic_claim_coverage.ClaimCoverageAssessment | None
    ) = None,
) -> AcademicReleaseAssessment:
    """Assess whether a checked academic draft may be presented.

    A recognised deterministic technical conflict blocks release. A material
    conflict with retrieved methodological guidance also blocks release.
    Clear contrary evidence from an assessed source claim blocks release of
    the unchanged draft. Absence of verification, support, or established
    methodological consistency does not by itself establish a conflict.
    """
    technical_statuses = [
        claim.verification.status
        for claim in technical_claims
    ]
    methodological_statuses = [
        claim.methodological_consistency.status
        for claim in technical_claims
        if (
            claim.methodological_consistency is not None
            and not standalone_methodology_is_contextually_superseded(
                claim.claim,
                discovered_claim_assessments,
            )
        )
    ]
    contextual_methodological_statuses = [
        assessment.contextual_methodological_consistency.status
        for assessment in (discovered_claim_assessments or [])
        if assessment.contextual_methodological_consistency is not None
    ]
    source_statuses = [
        claim.claim_assessment.status
        for claim in (source_claims or [])
        if claim.claim_assessment is not None
    ]

    if (
        academic_technical.TECHNICAL_STATUS_CONFLICT
        in technical_statuses
    ):
        return AcademicReleaseAssessment(
            status="blocked_technical_conflict",
            safe_to_present=False,
            reasons=[
                "At least one structured technical claim conflicts with "
                "deterministic technical verification."
            ],
        )

    if (
        academic_methodology.METHODOLOGICAL_STATUS_CONFLICT
        in (
            methodological_statuses
            + contextual_methodological_statuses
        )
    ):
        return AcademicReleaseAssessment(
            status="blocked_methodological_conflict",
            safe_to_present=False,
            reasons=[
                "At least one structured technical claim materially "
                "conflicts with retrieved methodological guidance."
            ],
        )

    if "claim_contradicted" in source_statuses:
        return AcademicReleaseAssessment(
            status="blocked_source_contradiction",
            safe_to_present=False,
            reasons=[
                "At least one assessed source claim has clear contrary "
                "evidence in the retrieved source."
            ],
        )

    if (
        claim_coverage is not None
        and claim_coverage.status
        == academic_claim_coverage.COVERAGE_STATUS_UNAVAILABLE
    ):
        return AcademicReleaseAssessment(
            status="checking_incomplete",
            safe_to_present=False,
            reasons=[
                "Independent technical-claim coverage checking could not be "
                "completed; this does not establish that the answer is wrong."
            ],
        )

    if (
        academic_technical.TECHNICAL_STATUS_NOT_VERIFIED
        in technical_statuses
    ):
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
            "No deterministic technical, methodological, or assessed "
            "source contradiction was identified."
        ],
    )


@dataclass
class AcademicFirstStageResult:
    draft: academic_chat.AcademicDraft
    local_guidance: LocalGuidanceResult
    claim_coverage: academic_claim_coverage.ClaimCoverageAssessment
    references: list[VerifiedReferenceProposal]
    source_claims: list[SourceClaimResult]
    technical_claims: list[TechnicalClaimResult]
    discovered_claim_assessments: list[DiscoveredClaimAssessment]
    release: AcademicReleaseAssessment

    @property
    def answer_draft(self) -> str:
        """Preserve the existing answer access without duplicating draft state."""
        return self.draft.answer_draft

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer_draft": self.answer_draft,
            "local_guidance": self.local_guidance.to_dict(),
            "claim_coverage": self.claim_coverage.to_dict(),
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
            "claim_context_assessments": [
                assessment.to_dict()
                for assessment in self.discovered_claim_assessments
            ],
            "release": self.release.to_dict(),
        }


def assess_academic_draft(
    draft: academic_chat.AcademicDraft,
    *,
    local_guidance: LocalGuidanceResult,
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
    methodological_assessor: Callable[..., Any] | None = None,
    claim_methodological_retriever: Callable[
        [str], LocalGuidanceResult
    ] | None = None,
    coverage_assessor: Callable[
        ..., academic_claim_coverage.ClaimCoverageAssessment
    ]
    | None = None,
    material_restriction_assessor: Callable[..., Any] | None = None,
) -> AcademicFirstStageResult:
    """Assess an already-generated AcademicDraft through the release pipeline.

    This stage receives neither the original question nor model/tokenizer
    handles. It operates only on the structured draft, application-owned local
    guidance, and the explicitly supplied verification components. Question-level
    guidance may be retained from generation, while an optional claim-specific
    retriever can obtain local guidance independently for each structured
    technical claim.
    """
    if reference_verifier is None:
        reference_verifier = verify_academic_reference

    if technical_verifier is None:
        technical_verifier = academic_technical.verify_technical_claim

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
                authorised_doi = _normalise_retrieval_doi(
                    retrieval_identity.doi
                )
                discovered_doi = _normalise_retrieval_doi(
                    location.doi if location is not None else None
                )

                if (
                    location is not None
                    and location.status == "location_found"
                    and (
                        discovered_doi is None
                        or discovered_doi != authorised_doi
                    )
                ):
                    source_discovery = SourceDiscoveryResult(
                        status="identity_mismatch",
                        location=None,
                        reasons=[
                            "Discovered source identity did not match the "
                            "retrieval-eligible DOI."
                        ],
                    )
                else:
                    source_discovery = SourceDiscoveryResult(
                        status="attempted",
                        location=location,
                        reasons=[
                            "Eligible retrieval identity was sent to "
                            "source discovery."
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

    claims_for_assessment = list(draft.technical_claims)
    discovered_claim_assessments: list[DiscoveredClaimAssessment] = []

    if coverage_assessor is None:
        claim_coverage = (
            academic_claim_coverage.ClaimCoverageAssessment.not_attempted(
                "No claim-coverage assessor was supplied."
            )
        )
    else:
        claim_coverage = coverage_assessor(
            answer_draft=draft.answer_draft,
            existing_claims=draft.technical_claims,
        )

        if not isinstance(
            claim_coverage,
            academic_claim_coverage.ClaimCoverageAssessment,
        ):
            raise TypeError(
                "Coverage assessor must return a ClaimCoverageAssessment."
            )

    if claim_coverage.result is not None:
        for discovered in claim_coverage.result.discovered_claims:
            source_context = (
                academic_claim_coverage.resolve_claim_source_context(
                    answer_draft=draft.answer_draft,
                    source_start=discovered.source_start,
                    source_end=discovered.source_end,
                )
            )

            material_restriction = None
            if material_restriction_assessor is not None:
                material_restriction = (
                    academic_claim_coverage.assess_material_restriction(
                        candidate_claim=discovered.claim,
                        source_context=source_context,
                        assessor=material_restriction_assessor,
                    )
                )

            contextual_methodological_consistency = None

            if (
                material_restriction is not None
                and material_restriction.material_restriction_omitted
                and claim_methodological_retriever is not None
                and methodological_assessor is not None
            ):
                contextual_guidance = claim_methodological_retriever(
                    _contextual_claim_methodological_query(
                        discovered.claim,
                        source_context,
                    )
                )

                if contextual_guidance.passages:
                    contextual_methodological_consistency = (
                        academic_methodology
                        .assess_contextual_methodological_consistency(
                            claim=discovered.claim,
                            source_context=source_context,
                            passages=contextual_guidance.passages,
                            assessor=methodological_assessor,
                        )
                    )

            discovered_claim_assessments.append(
                DiscoveredClaimAssessment(
                    discovered_claim=discovered,
                    source_context=source_context,
                    material_restriction=material_restriction,
                    contextual_methodological_consistency=(
                        contextual_methodological_consistency
                    ),
                )
            )

        assessed_keys = {
            _technical_claim_proposition_key(claim)
            for claim in claims_for_assessment
        }

        for discovered in claim_coverage.result.discovered_claims:
            claim = discovered.claim
            key = _technical_claim_proposition_key(claim)

            if key in assessed_keys:
                continue

            claims_for_assessment.append(claim)
            assessed_keys.add(key)

        # Compatibility for application-owned coverage results produced by
        # callers that supply missing claims without a discovery set.
        for claim in claim_coverage.result.missing_claims:
            key = _technical_claim_proposition_key(claim)

            if key in assessed_keys:
                continue

            claims_for_assessment.append(claim)
            assessed_keys.add(key)

    technical_claims = []

    for claim in claims_for_assessment:
        verification = technical_verifier(claim)
        methodological_consistency = None

        claim_guidance = local_guidance
        if claim_methodological_retriever is not None:
            claim_guidance = claim_methodological_retriever(
                _technical_claim_methodological_query(claim)
            )

        if (
            claim_guidance.passages
            and methodological_assessor is not None
        ):
            methodological_consistency = (
                academic_methodology.assess_methodological_consistency(
                    claim=claim,
                    passages=claim_guidance.passages,
                    assessor=methodological_assessor,
                )
            )

        technical_claims.append(
            TechnicalClaimResult(
                claim=claim,
                verification=verification,
                methodological_consistency=methodological_consistency,
            )
        )

    release = assess_academic_release(
        technical_claims,
        source_claims,
        discovered_claim_assessments,
        claim_coverage,
    )

    return AcademicFirstStageResult(
        draft=draft,
        local_guidance=local_guidance,
        claim_coverage=claim_coverage,
        references=verified_references,
        source_claims=source_claims,
        technical_claims=technical_claims,
        discovered_claim_assessments=discovered_claim_assessments,
        release=release,
    )


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
    methodological_retriever: Callable[
        [str], LocalGuidanceResult
    ] | None = None,
    methodological_assessor: Callable[..., Any] | None = None,
    claim_methodological_retriever: Callable[
        [str], LocalGuidanceResult
    ] | None = None,
    coverage_assessor: Callable[
        ..., academic_claim_coverage.ClaimCoverageAssessment
    ]
    | None = None,
    material_restriction_assessor: Callable[..., Any] | None = None,
) -> AcademicFirstStageResult:
    """
    Generate a local academic draft, verify its proposed references and
    deterministic technical claims, and resolve source-claim proposals to
    their corresponding verified-reference proposals.

    The full question remains within the local first stage: it is used by the
    local methodological retriever and local draft generator. Reference
    verification receives only the five bibliographic fields defined by the
    AcademicReference contract. Source-claim resolution is local and does not
    establish that a reference supports its associated claim. Claim-coverage
    assessment receives only the generated answer and its existing structured
    technical claims. Technical verification receives only each structured
    TechnicalClaim.
    """
    if draft_generator is None:
        draft_generator = academic_chat.generate_academic_draft

    if reference_verifier is None:
        reference_verifier = verify_academic_reference

    if technical_verifier is None:
        technical_verifier = academic_technical.verify_technical_claim

    if methodological_retriever is None:
        methodological_retriever = retrieve_methodological_context

    if claim_methodological_retriever is None:
        claim_methodological_retriever = retrieve_methodological_context

    local_guidance = methodological_retriever(question)

    if local_guidance.passages:
        draft = draft_generator(
            model,
            tokenizer,
            question,
            methodological_context=local_guidance.prompt_text,
        )
    else:
        draft = draft_generator(
            model,
            tokenizer,
            question,
        )

    return assess_academic_draft(
        draft,
        local_guidance=local_guidance,
        reference_verifier=reference_verifier,
        technical_verifier=technical_verifier,
        source_discoverer=source_discoverer,
        source_retriever=source_retriever,
        claim_locator=claim_locator,
        claim_assessor=claim_assessor,
        methodological_assessor=methodological_assessor,
        claim_methodological_retriever=claim_methodological_retriever,
        coverage_assessor=coverage_assessor,
        material_restriction_assessor=material_restriction_assessor,
    )
