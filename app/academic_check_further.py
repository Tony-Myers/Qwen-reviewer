"""
What an academic reader should be told about the evidence behind an answer.

The checking machinery reaches many fine-grained verdicts per answer. A reader
who asked "what is the difference between an ETI and an HDI?" needs three
things from them, at three levels of detail:

1.  A compact evidence statement. One of five states, worded for the reader
    and never for whoever maintains the guidance: no specific concern
    identified; further reading available; worth checking; outside the local
    guidance; or evidence check incomplete. No claim counts, scores or
    per-claim statuses at this level.
2.  Evidence and further reading. Curated references grouped by the
    methodological topic they belong to, in a compact form, with the full
    citation and the points the guidance did not settle behind a toggle.
3.  Technical checking details. Counts, routing decisions, points that were
    not routed, lost conditions and per-claim verdicts, for whoever is
    developing or auditing the checks.

This module makes no model call and changes no verdict. It reads what the
machinery decided -- the release decision, per-claim methodological
judgements, contextual assessments and reference verification -- and applies
fixed rules to it. The judge's prompt and schema, the release logic and the
claim-assessment pipeline are untouched.

Rules that matter, and why.

ROUTING. An unsettled point is offered further reading only from a section
that (a) was retrieved for the original question, (b) carries curated
references, and (c) the point was actually judged against. A section that
merely ranked highly in a claim's own retrieval is not enough: on the ETI/HDI
answer that routed "Both intervals contain 95% of the posterior probability"
to a section on credible intervals being mistaken for confidence intervals,
which is a recommendation the guidance never made. Points with no qualifying
section are kept in the technical details and generate no literature group.

WHAT THE ANSWER SAID. A point is shown as the answer's own sentence, taken
from the application-owned source sentence, wherever one exists. An atomic
claim is the checker's restatement and can lose a condition the answer
attached; presenting it as what the answer said misrepresents the answer.
Structured claims with no located sentence are labelled as summarised points.

CHECKING VERSUS CONCERN. A failure or gap in the checking is never presented
as a concern about the answer. "Worth checking" is reserved for an affirmative
signal: a judged conflict with the guidance, or a release blocked by a
conflict. An unmatched reference gets its own notice, because it is a fact
about a source given in support of the answer, not about the evidence for the
answer as a whole.

A FAILED JUDGEMENT IS NOT A GAP IN THE GUIDANCE. A methodological judgement
the model could not complete is recorded as "not established" with an
assessment_error. It says nothing about what the guidance establishes, so it
is never routed to further reading and never counted as a valid "not
established" judgement; it makes the evidence check incomplete instead. A
judgement that completed and found the point not established keeps its
meaning and is routed exactly as before.

The same holds for the other checks whose model output can be unusable: a
dropped-condition check that could not be completed is not a finding that no
condition was lost, and a source assessment that could not be completed is
not support, non-support or contradiction. Each makes the evidence check
incomplete and is kept, with its error, in the diagnostics only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import academic_methodology
import academic_orchestrator
import reviewer_notes


# 3: the citation notice counts only references a source claim points to.
# 4: a methodological judgement that could not be completed (assessment_error)
#    makes the check incomplete and is not routed to further reading.
# 5: so do a dropped-condition check and a source assessment that could not
#    be completed; the incomplete wording covers any check.
# 6: a revision withheld because it was not shown to resolve a source
#    contradiction is reported as a reason for withholding.
RULES_VERSION = "6"

STATE_NO_CONCERN = "no_specific_concern"
STATE_FURTHER_READING = "further_reading"
STATE_WORTH_CHECKING = "worth_checking"
STATE_OUTSIDE = "outside_guidance"
STATE_INCOMPLETE = "incomplete"

TITLES = {
    STATE_NO_CONCERN: "No specific concern identified",
    STATE_FURTHER_READING: "Further reading available",
    STATE_WORTH_CHECKING: "Worth checking",
    STATE_OUTSIDE: "Outside the local guidance",
    STATE_INCOMPLETE: "Evidence check incomplete",
}

# Incomplete checking says nothing about whether the answer is right. The
# reader is told that once, here, in place of the older notice beside the
# answer (which now sits under Technical checking details).
INCOMPLETE_SUMMARY = ("Some of the checks on this answer could not be "
                      "completed.")
INCOMPLETE_SECONDARY = ("This does not mean the answer is wrong, but some "
                        "points could not be fully checked.")
# Added to the secondary line when a source given in support of the answer
# was located but could not be checked against it.
SOURCE_INCOMPLETE_NOTE = ("A source given in support of this answer could not "
                          "be fully checked against it.")

ABOUT = (
    "Academic Chat compares parts of its answer with locally curated "
    "methodological guidance. Agreement with that guidance is not independent "
    "verification. Where the local guidance does not settle a point, relevant "
    "curated references may be provided for further checking."
)

# A methodological conflict is a semantic judgement and no longer blocks
# release (release_allowed_with_methodological_conflict); the answer is shown
# and the conflict is reported here as worth checking.
METHODOLOGICAL_CONFLICT_SUMMARY = (
    "A point in this answer may warrant closer checking: the local "
    "methodological guidance appears to say something different.")
INCOMPLETE_WITH_CONCERN_SECONDARY = (
    "Some of the checking could not be completed, so this may not be the "
    "only point worth checking.")

# Release statuses that withhold the answer: deterministic or source evidence.
_BLOCKED_SUMMARIES = {
    "blocked_technical_conflict": (
        "A technical statement in this answer did not pass an automated "
        "check and may warrant closer checking."),
    "blocked_source_contradiction": (
        "A source associated with this answer appears to say something "
        "different from it, so the point may warrant closer checking."),
    # Set by reconciliation, not by the first-stage release.
    "blocked_unresolved_source_contradiction": (
        "A source given in support of the original answer appeared to "
        "contradict it, and the revised answer could not be confirmed "
        "against that source."),
}
UNRESOLVED_SOURCE_CONTRADICTION = "blocked_unresolved_source_contradiction"
# Said only when a revised claim citing that source could not be re-checked,
# not when the citation was dropped or the source did not support the claim.
RETRY_MAY_HELP = ("Trying again may help if the source could not be reached "
                  "or checked.")

POINT_ANSWER_SENTENCE = "answer_sentence"
POINT_SUMMARISED = "summarised_point"


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class Point:
    """Something the answer said, as the reader should see it."""

    text: str
    kind: str                      # POINT_ANSWER_SENTENCE or POINT_SUMMARISED

    def to_dict(self) -> Dict[str, str]:
        return {"text": self.text, "kind": self.kind}


@dataclass
class ReadingGroup:
    """Curated references for one methodological topic, and the points they bear on."""

    note: str
    heading: str
    references: List[reviewer_notes.Reference]
    points: List[Point] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.heading or self.note,
            "note": self.note,
            "heading": self.heading,
            "references": [r.to_dict() for r in self.references],
            "points": [p.to_dict() for p in self.points],
        }


@dataclass
class CheckFurtherAssessment:
    state: str
    summary: str
    secondary: str
    worth_checking: List[Dict[str, str]]
    citation_notice: Optional[Dict[str, Any]]
    groups: List[ReadingGroup]
    diagnostics: Dict[str, Any]

    @property
    def title(self) -> str:
        return TITLES[self.state]

    @property
    def source_count(self) -> int:
        seen = set()
        for group in self.groups:
            for ref in group.references:
                seen.add(_reference_key(ref))
        return len(seen)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rules_version": RULES_VERSION,
            "state": self.state,
            "title": self.title,
            "summary": self.summary,
            "secondary": self.secondary,
            "worth_checking": list(self.worth_checking),
            "citation_notice": self.citation_notice,
            "further_reading": [g.to_dict() for g in self.groups],
            "source_count": self.source_count,
            "about": ABOUT,
            "diagnostics": self.diagnostics,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Case, spacing, quotes and final punctuation only; wording is kept."""
    text = re.sub(r"[\"'‘’“”]", "", text or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text.rstrip(" .;:")


def _reference_key(ref: reviewer_notes.Reference) -> str:
    return ref.doi.lower() or ref.url or ref.isbn or ref.cite


def linked_reference_indices(result) -> set:
    """Positions of the proposed references that a source claim points to.

    The draft proposes references as a list and, separately, source claims
    that each name one entry by its position (reference_index, checked
    against the list when the draft is parsed). That application-owned link
    is the only record that a reference was given in support of a claim; a
    proposal no source claim points to is not shown to the reader as a
    reference and does not trigger the citation notice. It stays in the
    technical details. No model judges relevance here.
    """
    linked = set()
    for item in getattr(result, "source_claims", None) or []:
        index = getattr(getattr(item, "claim", None), "reference_index", None)
        if isinstance(index, int) and not isinstance(index, bool):
            linked.add(index)
    return linked


def _section(passage) -> Tuple[str, str]:
    return (passage.note, passage.heading)


def _best(passages, allowed=None):
    """Highest-scoring passage, optionally among allowed sections only."""
    pool = [p for p in passages if allowed is None or _section(p) in allowed]
    if not pool:
        return None
    return max(pool, key=lambda p: (p.score or 0.0))


def _citation_label(proposed) -> str:
    parts = [
        getattr(proposed, "author", None) or "",
        f"({proposed.year})" if getattr(proposed, "year", None) else "",
        getattr(proposed, "title", None) or "",
    ]
    label = " ".join(p for p in parts if p).strip()
    doi = getattr(proposed, "doi", None)
    if doi:
        label = f"{label} doi:{doi}".strip()
    return label or "an unnamed source"


@dataclass
class _Judgement:
    statement: str
    status: str
    passages: list
    reasons: list
    point: Point
    contextual: bool
    # Non-empty when the judgement could not be completed: its status is then
    # not a judgement about the guidance at all.
    error: str = ""

    @property
    def failed(self) -> bool:
        return bool(self.error)


def _point_for(claim, statement: str, sentence_by_claim) -> Point:
    sentence = sentence_by_claim(claim, statement)
    if sentence:
        return Point(sentence.strip(), POINT_ANSWER_SENTENCE)
    return Point(statement.strip(), POINT_SUMMARISED)


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

def assess_check_further(
    result: Any,
    index: reviewer_notes.NotesIndex,
    *,
    source_contradiction_resolution: Any = None,
) -> CheckFurtherAssessment:
    """Turn a checked Academic Chat result into what the reader is told.

    ``result`` is an AcademicFirstStageResult; for a reconciled answer pass the
    attempt as presented (AcademicReconciliationResult.presented), whose
    release may be the reconciliation's own. ``index`` should be the index that
    supplied the guidance. ``source_contradiction_resolution`` is the
    reconciliation's record of how a revision fared against the sources that
    contradicted the first attempt, when there is one.
    """
    consistent = academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
    conflict = academic_methodology.METHODOLOGICAL_STATUS_CONFLICT

    assessments = list(result.discovered_claim_assessments or [])
    guidance = list(getattr(result.local_guidance, "passages", []) or [])
    question_sections = []
    for passage in guidance:
        if _section(passage) not in question_sections:
            question_sections.append(_section(passage))

    # The answer's own sentence for a claim, wherever the coverage step
    # located one: by identity of the claim object first, as the release
    # logic matches them, then by identical wording.
    def sentence_by_claim(claim, statement):
        for item in assessments:
            if item.discovered_claim.claim is claim or item.discovered_claim.claim == claim:
                return item.source_context.source_sentence
        key = _normalise(statement)
        for item in assessments:
            if _normalise(item.discovered_claim.claim.statement) == key:
                return item.source_context.source_sentence
        return ""

    # ---- every methodological judgement, collected as the release does -----
    judgements: List[_Judgement] = []
    for item in result.technical_claims or []:
        method = item.methodological_consistency
        if method is None:
            continue
        if academic_orchestrator.standalone_methodology_is_contextually_superseded(
                item.claim, assessments):
            continue
        judgements.append(_Judgement(
            item.claim.statement, method.status, list(method.passages),
            list(getattr(method, "reasons", []) or []),
            _point_for(item.claim, item.claim.statement, sentence_by_claim),
            False, getattr(method, "assessment_error", "") or ""))
    for item in assessments:
        method = item.contextual_methodological_consistency
        if method is None:
            continue
        judgements.append(_Judgement(
            item.discovered_claim.claim.statement, method.status,
            list(method.passages), list(getattr(method, "reasons", []) or []),
            Point(item.source_context.source_sentence.strip(), POINT_ANSWER_SENTENCE),
            True, getattr(method, "assessment_error", "") or ""))

    # Judgements that could not be completed are kept apart: they make the
    # check incomplete and take no part in settling or routing a point.
    failed = [j for j in judgements if j.failed]
    completed = [j for j in judgements if not j.failed]

    settled = {_normalise(j.statement) for j in completed if j.status == consistent}
    conflicts = [j for j in completed if j.status == conflict]
    conflict_keys = {_normalise(j.statement) for j in conflicts}

    # ---- unsettled points, routed only to qualifying sections ---------------
    sourced = {
        section for section in question_sections
        if index.references_for(*section)
    }
    groups: Dict[Tuple[str, str], ReadingGroup] = {}
    order: List[Tuple[str, str]] = []
    placed_points = set()
    routing, unrouted = [], []
    unsettled_keys = set()
    for j in completed:
        key = _normalise(j.statement)
        if j.status in (consistent, conflict) or key in settled or key in conflict_keys:
            continue
        unsettled_keys.add(key)
        best = _best(j.passages, allowed=sourced)
        if best is None:
            nearest = _best(j.passages)
            reason = (
                "no section judged against it was both retrieved for the "
                "question and curated with references")
            unrouted.append({
                "point": j.point.text,
                "kind": j.point.kind,
                "statement": j.statement,
                "nearest_section": (
                    f"{nearest.note} - {nearest.heading}" if nearest else None),
                "reason": reason,
            })
            routing.append({"statement": j.statement, "routed_to": None,
                            "reason": reason})
            continue
        section = _section(best)
        if section not in groups:
            groups[section] = ReadingGroup(
                note=section[0], heading=section[1],
                references=_dedupe(index.references_for(*section)))
            order.append(section)
        point_key = _normalise(j.point.text)
        if point_key not in placed_points:
            placed_points.add(point_key)
            groups[section].points.append(j.point)
        routing.append({"statement": j.statement,
                        "routed_to": f"{section[0]} - {section[1]}",
                        "reason": "judged against a curated section retrieved "
                                  "for the question"})
    group_list = [groups[s] for s in order]

    # ---- conditions lost when a claim was separated from the answer --------
    lost_conditions = []
    for item in assessments:
        restriction = item.material_restriction
        if restriction is None or not restriction.material_restriction_omitted:
            continue
        method = item.contextual_methodological_consistency
        lost_conditions.append({
            "answer_sentence": item.source_context.source_sentence,
            "atomic_claim": item.discovered_claim.claim.statement,
            "contextual_status": method.status if method is not None else None,
            "contextual_reasons": list(method.reasons) if method is not None else [],
            "contextual_assessment_error": (
                getattr(method, "assessment_error", "") or ""
                if method is not None else ""),
        })

    # ---- checks whose model output could not be used ------------------------
    # A dropped-condition check that could not be completed: whether the
    # atomic claim lost a condition is unknown, not "no condition lost".
    failed_restrictions = []
    for item in assessments:
        error = getattr(item.material_restriction, "assessment_error", "") or ""
        if error:
            failed_restrictions.append({
                "answer_sentence": item.source_context.source_sentence,
                "atomic_claim": item.discovered_claim.claim.statement,
                "assessment_error": error,
            })
    # A source assessment that could not be completed: the located evidence
    # stays in the technical details; no support status is implied.
    failed_sources = []
    references = list(result.references or [])
    for item in getattr(result, "source_claims", None) or []:
        error = getattr(item, "claim_assessment_error", "") or ""
        if not error:
            continue
        index = getattr(item.claim, "reference_index", None)
        proposal = (references[index] if isinstance(index, int)
                    and 0 <= index < len(references) else None)
        location = getattr(item, "claim_location", None)
        evidence = list(getattr(location, "evidence", None) or [])
        failed_sources.append({
            "claim": item.claim.claim,
            "reference": (_citation_label(proposal.proposed_reference)
                          if proposal is not None else ""),
            "located_passages": len(evidence),
            "pages": sorted({e.page_number for e in evidence
                             if getattr(e, "page_number", None) is not None}),
            "assessment_error": error,
        })

    # ---- a source given in support that does not match a record ----------
    unmatched, conflicting, unlinked = [], [], []
    linked = linked_reference_indices(result)
    for position, proposal in enumerate(result.references or []):
        if position not in linked:
            unlinked.append(_citation_label(proposal.proposed_reference))
            continue
        verification = proposal.verification
        status = getattr(verification.crossref_verification, "status", "")
        label = _citation_label(proposal.proposed_reference)
        if verification.identity_conflict:
            conflicting.append(label)
        elif status != "verified":
            unmatched.append(label)
    citation_notice = None
    if unmatched or conflicting:
        parts = []
        if unmatched:
            parts.append(
                "A source given in support of this answer could not be "
                "matched to a published record." if len(unmatched) == 1 else
                "Some sources given in support of this answer could not be "
                "matched to a published record.")
        if conflicting:
            parts.append(
                "The details of a source given in support of this answer "
                "conflict with the published record." if len(conflicting) == 1
                else "The details of some sources given in support of this "
                "answer conflict with the published record.")
        citation_notice = {
            "title": "Citation check",
            "message": " ".join(parts) + " Check the citation before relying on it.",
            "unmatched": unmatched,
            "conflicting": conflicting,
        }

    # ---- state ---------------------------------------------------------------
    release = result.release
    secondary = ""
    worth_checking: List[Dict[str, str]] = []
    # A recorded conflict is a concern about the answer and is reported even
    # when other checking was incomplete; incomplete checking on its own is
    # never presented as a concern.
    checking_incomplete = (release.status == "checking_incomplete" or bool(failed)
                           or bool(failed_restrictions) or bool(failed_sources))
    source_note = (" " + SOURCE_INCOMPLETE_NOTE) if failed_sources else ""
    if release.status in _BLOCKED_SUMMARIES or conflicts:
        state = STATE_WORTH_CHECKING
        summary = _BLOCKED_SUMMARIES.get(
            release.status, METHODOLOGICAL_CONFLICT_SUMMARY)
        if checking_incomplete:
            secondary = INCOMPLETE_WITH_CONCERN_SECONDARY + source_note
        seen = set()
        for j in conflicts:
            key = _normalise(j.point.text)
            if key in seen:
                continue
            seen.add(key)
            nearest = _best(j.passages)
            worth_checking.append({
                "text": j.point.text,
                "kind": j.point.kind,
                "topic": nearest.heading if nearest else "",
                "explanation": (
                    "The local methodological guidance appears to say "
                    "something different about this point."),
            })
    elif checking_incomplete:
        state = STATE_INCOMPLETE
        summary = INCOMPLETE_SUMMARY
        secondary = INCOMPLETE_SECONDARY + source_note
    elif not guidance:
        state = STATE_OUTSIDE
        summary = ("This question is not covered by the local methodological "
                   "guidance, so the answer has not been compared with it.")
    elif not judgements:
        state = STATE_OUTSIDE
        summary = ("The answer has not been compared with the local "
                   "methodological guidance, so its agreement with that "
                   "guidance is unknown.")
    elif group_list:
        state = STATE_FURTHER_READING
        summary = (
            "Parts of this answer align with the local methodological "
            "guidance, while some details go beyond what that guidance covers."
            if settled else
            "Some details of this answer go beyond what the local "
            "methodological guidance covers.")
        # The source count shown beneath the summary already says this;
        # repeating it in a second sentence added length and nothing else.
        secondary = ""
    else:
        state = STATE_NO_CONCERN
        summary = ("Nothing in the local methodological guidance gave a clear "
                   "reason to question this answer.")
        if unsettled_keys:
            secondary = ("Some details go beyond what the local methodological "
                         "guidance covers, and no curated sources are "
                         "available for them yet.")

    # A revision withheld because it was not shown to resolve a source
    # contradiction: the reason is the summary itself. Trying again is
    # suggested only when a revised claim citing that source could not be
    # re-checked; it would not help a dropped citation or an unsupported claim.
    if release.status == UNRESOLVED_SOURCE_CONTRADICTION:
        retry = False
        for source in getattr(source_contradiction_resolution, "sources", None) or []:
            if getattr(source, "outcome", "") != "resolution_not_established":
                continue
            for claim in getattr(source, "revised_claims", None) or []:
                if claim.get("claim_assessment") is None:
                    retry = True
        secondary = RETRY_MAY_HELP if retry else ""

    diagnostics = {
        "rules_version": RULES_VERSION,
        "release_status": release.status,
        "counts": {
            "judgements": len(judgements),
            "consistent": sum(1 for j in judgements if j.status == consistent),
            "conflict": len(conflicts),
            "not_established": sum(
                1 for j in completed if j.status not in (consistent, conflict)),
            "failed_methodology_checks": len(failed),
            "failed_restriction_checks": len(failed_restrictions),
            "failed_source_assessments": len(failed_sources),
            "unsettled_statements": len(unsettled_keys),
            "points_shown": sum(len(g.points) for g in group_list),
            "unrouted": len(unrouted),
            "lost_conditions": len(lost_conditions),
        },
        "question_sections": [f"{n} - {h}" for n, h in question_sections],
        "sourced_question_sections": [f"{n} - {h}" for n, h in question_sections
                                      if (n, h) in sourced],
        "routing": routing,
        "unrouted": unrouted,
        "lost_conditions": lost_conditions,
        "conflicts": [
            {"statement": j.statement, "answer_text": j.point.text,
             "reasons": j.reasons,
             "sections": [f"{p.note} - {p.heading}" for p in j.passages]}
            for j in conflicts
        ],
        "unlinked_references": unlinked,
        "failed_methodology_checks": [
            {"statement": j.statement, "answer_text": j.point.text,
             "contextual": j.contextual, "assessment_error": j.error,
             "sections": [f"{p.note} - {p.heading}" for p in j.passages]}
            for j in failed
        ],
        "failed_restriction_checks": failed_restrictions,
        "failed_source_assessments": failed_sources,
    }

    return CheckFurtherAssessment(
        state=state,
        summary=summary,
        secondary=secondary,
        worth_checking=worth_checking,
        citation_notice=citation_notice,
        groups=group_list,
        diagnostics=diagnostics,
    )


def incomplete_assessment(error: str) -> Dict[str, Any]:
    """What the reader is told when this assessment itself fails."""
    return {
        "rules_version": RULES_VERSION,
        "state": STATE_INCOMPLETE,
        "title": TITLES[STATE_INCOMPLETE],
        "summary": INCOMPLETE_SUMMARY,
        "secondary": INCOMPLETE_SECONDARY,
        "worth_checking": [],
        "citation_notice": None,
        "further_reading": [],
        "source_count": 0,
        "about": ABOUT,
        "diagnostics": {"rules_version": RULES_VERSION, "error": error},
    }


def _dedupe(refs):
    seen, out = set(), []
    for ref in refs:
        key = _reference_key(ref)
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out
