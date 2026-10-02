"""
One-attempt reconciliation lifecycle for Academic Chat.

This layer composes first-stage generation/checking with bounded correction
extraction, one local revision attempt, and fresh reassessment.

It does not perform generation, verification, or first-stage release
assessment itself. The original user question is used only by the supplied
first-stage runner. Reconciliation operates on the retained AcademicDraft and
application-owned checking results.

It also owns the presentation decision: whether the reader is shown the
answer (release), shown it qualified as incompletely checked (qualified), or
not shown it (withheld). The page renders that decision and does not derive
its own from release statuses.

It owns one release decision of its own. Once a source contradiction has
withheld the first attempt, the absence of a contradiction in the revised
attempt is not evidence that it was resolved: the source may not have been
re-checked at all. A revision clears that block only through a completed
favourable reassessment of a claim citing each source that contradicted the
first attempt. Sources are matched by application-owned normalised DOI; no
claim wording is compared and no model is asked.
"""

from dataclasses import dataclass, field, replace
from typing import Any, Callable

import academic_chat
import academic_orchestrator
import academic_reconciliation


# The revised attempt did not itself establish a contradiction, but it was not
# shown to resolve a source contradiction that withheld the first attempt.
RELEASE_STATUS_UNRESOLVED_SOURCE_CONTRADICTION = (
    "blocked_unresolved_source_contradiction"
)

SOURCE_CONTRADICTION_STATUS = "blocked_source_contradiction"

RESOLUTION_POSITIVELY_CLEARED = "positively_cleared"
RESOLUTION_STILL_CONTRADICTED = "still_contradicted"
RESOLUTION_NOT_ESTABLISHED = "resolution_not_established"

# Only a completed reassessment with one of these outcomes clears a source.
_CLEARING_ASSESSMENTS = ("claim_supported", "claim_partially_supported")

# Revised release statuses that already withhold the revision on their own
# evidence. They are kept as they are; the unresolved state only replaces a
# release that would otherwise let the revision be presented.
_REVISED_BLOCKS = ("blocked_technical_conflict", SOURCE_CONTRADICTION_STATUS)


def _doi(value: str | None) -> str | None:
    return academic_orchestrator._normalise_retrieval_doi(value)


def _cited_dois(source_claim: Any) -> set[str]:
    """Every application-owned DOI a source claim is associated with.

    The proposed reference's DOI counts whether or not it could be verified or
    retrieved, so an unverifiable or unreachable re-citation is still seen as
    a citation of that source that was not successfully re-checked.
    """
    dois = set()
    reference = getattr(source_claim, "reference", None)
    proposed = getattr(reference, "proposed_reference", None)
    dois.add(_doi(getattr(proposed, "doi", None)))
    verification = getattr(reference, "verification", None)
    crossref = getattr(verification, "crossref_verification", None)
    if getattr(crossref, "status", None) == "verified":
        dois.add(_doi(getattr(getattr(crossref, "candidate", None), "doi", None)))
    identity = getattr(source_claim, "retrieval_identity", None)
    dois.add(_doi(getattr(identity, "doi", None)))
    dois.discard(None)
    return dois


def _assessment_status(source_claim: Any) -> str | None:
    assessment = getattr(source_claim, "claim_assessment", None)
    return getattr(assessment, "status", None)


def _revised_claim_state(source_claim: Any) -> dict[str, Any]:
    retrieval = getattr(source_claim, "source_retrieval", None)
    location = getattr(source_claim, "claim_location", None)
    return {
        "claim": source_claim.claim.claim,
        "retrieval_identity": getattr(
            getattr(source_claim, "retrieval_identity", None), "status", None),
        "source_retrieval": getattr(retrieval, "status", None),
        "claim_location": getattr(location, "status", None),
        "claim_assessment": _assessment_status(source_claim),
        "claim_assessment_error": (
            getattr(source_claim, "claim_assessment_error", "") or ""),
    }


@dataclass
class ContradictedSourceResolution:
    """How one source that contradicted the first attempt fared in the revision."""

    doi: str | None
    outcome: str
    original_claims: list[dict[str, Any]]
    revised_claims: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "outcome": self.outcome,
            "original_claims": list(self.original_claims),
            "revised_claims": list(self.revised_claims),
        }


@dataclass
class SourceContradictionResolution:
    """Whether a revision resolved the source contradictions that withheld it."""

    status: str
    sources: list[ContradictedSourceResolution] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "sources": [source.to_dict() for source in self.sources],
        }


def assess_source_contradiction_resolution(
    initial: Any,
    revised: Any,
) -> SourceContradictionResolution | None:
    """Decide whether a revision resolved the first attempt's source contradictions.

    Returns None unless the first attempt was withheld by a source
    contradiction and a revision was assessed. Each source that contradicted
    the first attempt is identified by normalised DOI. It is positively
    cleared only when the revision still cites it and every revised claim
    citing it completed reassessment as supported or partially supported. A
    revised contradiction is still a contradiction. Anything else -- no
    citation, an ineligible or unreachable source, an unlocated claim, an
    assessment not completed, or "not supported" -- leaves resolution not
    established.
    """
    if revised is None:
        return None
    if getattr(getattr(initial, "release", None), "status", None) != (
        SOURCE_CONTRADICTION_STATUS
    ):
        return None

    contradicted: dict[str | None, list[dict[str, Any]]] = {}
    for item in getattr(initial, "source_claims", None) or []:
        if _assessment_status(item) != "claim_contradicted":
            continue
        identity_doi = _doi(getattr(getattr(item, "retrieval_identity", None), "doi", None))
        dois = {identity_doi} if identity_doi else _cited_dois(item)
        evidence = [
            evidence_item.to_dict()
            for evidence_item in getattr(item.claim_assessment, "evidence", None) or []
        ]
        for doi in dois or {None}:
            contradicted.setdefault(doi, []).append({
                "claim": item.claim.claim,
                "evidence": evidence,
            })

    if not contradicted:
        return None

    revised_claims = list(getattr(revised, "source_claims", None) or [])
    sources = []
    for doi, originals in contradicted.items():
        citing = [item for item in revised_claims
                  if doi is not None and doi in _cited_dois(item)]
        statuses = [_assessment_status(item) for item in citing]
        if "claim_contradicted" in statuses:
            outcome = RESOLUTION_STILL_CONTRADICTED
        elif citing and all(status in _CLEARING_ASSESSMENTS for status in statuses):
            outcome = RESOLUTION_POSITIVELY_CLEARED
        else:
            outcome = RESOLUTION_NOT_ESTABLISHED
        sources.append(ContradictedSourceResolution(
            doi=doi,
            outcome=outcome,
            original_claims=originals,
            revised_claims=[_revised_claim_state(item) for item in citing],
        ))

    if getattr(revised.release, "status", None) == SOURCE_CONTRADICTION_STATUS or any(
        source.outcome == RESOLUTION_STILL_CONTRADICTED for source in sources
    ):
        status = RESOLUTION_STILL_CONTRADICTED
    elif all(source.outcome == RESOLUTION_POSITIVELY_CLEARED for source in sources):
        status = RESOLUTION_POSITIVELY_CLEARED
    else:
        status = RESOLUTION_NOT_ESTABLISHED

    return SourceContradictionResolution(status=status, sources=sources)


PRESENTATION_RELEASE = "release"
PRESENTATION_QUALIFIED = "qualified"
PRESENTATION_WITHHELD = "withheld"

# The one release status under which a first answer may still be shown,
# qualified as incompletely checked: no blocking problem was established, but
# a check required before ordinary release could not be completed.
QUALIFIED_FIRST_ATTEMPT_STATUS = "checking_incomplete"


@dataclass
class PresentationDecision:
    """Whether and how the reader is shown the answer.

    reason is the release status that decided it, in the existing vocabulary.
    """

    mode: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "reason": self.reason}


def decide_presentation(release: Any, *, revised: bool) -> PresentationDecision:
    """Decide presentation from the final release and whether a revision was made.

    A first answer cleared for ordinary release is released. A first answer
    whose checking was incomplete, with no blocking problem established, is
    shown qualified -- a deliberate product decision. Any other first answer
    is withheld.

    A revision exists only because a blocking problem was established, so it
    is shown only when cleared for ordinary release and is otherwise withheld.
    A revision is never shown qualified.
    """
    status = getattr(release, "status", None) or ""
    if getattr(release, "safe_to_present", False) is True:
        return PresentationDecision(PRESENTATION_RELEASE, status)
    if not revised and status == QUALIFIED_FIRST_ATTEMPT_STATUS:
        return PresentationDecision(PRESENTATION_QUALIFIED, status)
    return PresentationDecision(PRESENTATION_WITHHELD, status)


@dataclass
class AcademicReconciliationResult:
    """Audit both attempts while exposing the independently checked final one."""

    initial: academic_orchestrator.AcademicFirstStageResult
    revised: academic_orchestrator.AcademicFirstStageResult | None
    revision_attempted: bool
    source_contradiction_resolution: SourceContradictionResolution | None = None

    @property
    def final(self) -> academic_orchestrator.AcademicFirstStageResult:
        if self.revised is not None:
            return self.revised
        return self.initial

    @property
    def unresolved_release(
        self,
    ) -> academic_orchestrator.AcademicReleaseAssessment | None:
        """The reconciliation-level release, when it overrides the revision's own.

        Set only when a source contradiction withheld the first attempt, the
        revised attempt would otherwise be presented, and resolution of that
        contradiction was not established. The revised attempt's own release
        is left untouched for the audit.
        """
        resolution = self.source_contradiction_resolution
        if (
            resolution is None
            or resolution.status != RESOLUTION_NOT_ESTABLISHED
            or self.revised is None
            or getattr(self.revised.release, "status", None) in _REVISED_BLOCKS
        ):
            return None
        return academic_orchestrator.AcademicReleaseAssessment(
            status=RELEASE_STATUS_UNRESOLVED_SOURCE_CONTRADICTION,
            safe_to_present=False,
            reasons=[
                "A source contradiction withheld the first attempt, and the "
                "revision was not shown to resolve it: every source that "
                "contradicted the first attempt must be re-cited and its "
                "completed reassessment must be supported or partially "
                "supported."
            ],
        )

    @property
    def presented(self) -> Any:
        """The final attempt as presented: the revision under any reconciliation release."""
        release = self.unresolved_release
        if release is None:
            return self.final
        return replace(self.final, release=release)

    @property
    def presentation(self) -> PresentationDecision:
        """The single application-owned decision on what the reader is shown."""
        return decide_presentation(
            getattr(self.presented, "release", None),
            revised=self.revised is not None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the final result plus the retained reconciliation audit."""
        result = self.final.to_dict()
        release = self.unresolved_release
        if release is not None:
            result["release"] = release.to_dict()
        result["presentation"] = self.presentation.to_dict()
        result["reconciliation"] = {
            "revision_attempted": self.revision_attempted,
            "initial": self.initial.to_dict(),
            "revised": (
                self.revised.to_dict()
                if self.revised is not None
                else None
            ),
        }
        if self.source_contradiction_resolution is not None:
            result["reconciliation"]["source_contradiction_resolution"] = (
                self.source_contradiction_resolution.to_dict()
            )
        return result


def run_academic_reconciliation(
    model: Any,
    tokenizer: Any,
    question: str,
    *,
    first_stage_runner: Callable[..., academic_orchestrator.AcademicFirstStageResult],
    correction_extractor: Callable[..., academic_reconciliation.AcademicCorrectionSet],
    revision_generator: Callable[..., academic_chat.AcademicDraft],
    draft_assessor: Callable[..., academic_orchestrator.AcademicFirstStageResult],
) -> AcademicReconciliationResult:
    """Run first-stage checking and, when warranted, one bounded revision.

    A safe initial result is returned unchanged. A blocked result is revised
    only when independent checking produced bounded correction material.

    A revised AcademicDraft is assessed from scratch. The revised release
    decision is not inherited from the initial attempt, and this coordinator
    never performs a second revision. When a source contradiction withheld
    the first attempt, the revision may be presented only if that
    contradiction is shown to be resolved (see
    assess_source_contradiction_resolution).
    """
    initial = first_stage_runner(
        model,
        tokenizer,
        question,
    )

    if initial.release.safe_to_present:
        return AcademicReconciliationResult(
            initial=initial,
            revised=None,
            revision_attempted=False,
        )

    corrections = correction_extractor(
        technical_claims=initial.technical_claims,
        source_claims=initial.source_claims,
        discovered_claim_assessments=(
            initial.discovered_claim_assessments
        ),
    )

    if corrections.is_empty():
        return AcademicReconciliationResult(
            initial=initial,
            revised=None,
            revision_attempted=False,
        )

    revised_draft = revision_generator(
        model,
        tokenizer,
        initial.draft,
        corrections,
    )

    revised = draft_assessor(
        revised_draft,
        local_guidance=initial.local_guidance,
    )

    return AcademicReconciliationResult(
        initial=initial,
        revised=revised,
        revision_attempted=True,
        source_contradiction_resolution=(
            assess_source_contradiction_resolution(initial, revised)
        ),
    )
