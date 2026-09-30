"""
When should the reader check an Academic Chat answer further, and where?

The checking machinery produces a great deal of evidence: per-claim technical
and methodological statuses, contextual assessments, reference verification
and a release decision. It does not say, in terms a reader can act on,
whether this answer needs checking and against what. This module does. It
makes no model call and changes no verdict: it reads what the machinery
already decided and applies a small set of fixed rules to it.

Three things it is careful about.

1.  CONSISTENCY WITH THE NOTES IS NOT TRUTH.
    The notes are one person's curated guidance. A claim that agrees with them
    is consistent with that guidance, which is worth knowing and is not
    verification. The best outcome is therefore worded as "consistent with
    your notes", never as "verified", and it still lists where to confirm it.

2.  "NOT ESTABLISHED" MOSTLY MEANS THE NOTES ARE SILENT.
    On the ETI/HDI question a textbook definition of the HDI was marked not
    established because the note words it differently. Reporting each such
    claim as doubtful repeats the noise the verification panel already has.
    Instead the unsettled claims are grouped under the note section closest
    to them, and each group carries that section's curated references: the
    reader is told where to check, once per topic, not once per sentence.

3.  EVERY "CHECK THIS" SAYS WHERE.
    A rule that tells a reader to check something and gives them nowhere to
    look is not a rule they can follow. When the relevant notes carry no
    curated references yet, that is itself reported.

The rules are listed in RULES, in order of severity, and are returned with
every assessment so the interface can show why a message appeared.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import academic_methodology
import academic_orchestrator
import reviewer_notes


RULES_VERSION = "1"

LEVEL_SETTLED = "consistent_with_notes"
LEVEL_ADVISED = "check_advised"
LEVEL_NEEDED = "check_needed"

_LEVEL_ORDER = {LEVEL_SETTLED: 0, LEVEL_ADVISED: 1, LEVEL_NEEDED: 2}

HEADLINES = {
    LEVEL_NEEDED: "Check this answer before using it.",
    LEVEL_ADVISED: (
        "Parts of this answer are not settled by your notes. Check them "
        "against the sources listed."
    ),
    LEVEL_SETTLED: (
        "Every claim that was checked is consistent with your notes. Your "
        "notes are guidance rather than proof; the sources below are where "
        "to confirm it."
    ),
}

# (rule id, level, when it applies). Kept as data so the interface can show
# the reader the rule that produced a message, not just the message.
RULES: Tuple[Tuple[str, str, str], ...] = (
    ("release_blocked", LEVEL_NEEDED,
     "The checks blocked the answer, or could not finish checking it."),
    ("notes_conflict", LEVEL_NEEDED,
     "Your notes say something incompatible with part of the answer."),
    ("reference_not_confirmed", LEVEL_NEEDED,
     "The answer cites a source that could not be matched to a published "
     "record, or whose details conflict with the record."),
    ("no_guidance", LEVEL_NEEDED,
     "Nothing in your notes addresses the question, so no part of the answer "
     "was checked against them."),
    ("nothing_checked", LEVEL_ADVISED,
     "Your notes were consulted, but no claim in the answer was judged "
     "against them."),
    ("not_settled_by_notes", LEVEL_ADVISED,
     "Some claims are neither supported nor contradicted by your notes."),
    ("condition_not_resolved", LEVEL_ADVISED,
     "A claim lost a condition when it was separated from the answer, and "
     "the check made with the condition restored did not find it consistent."),
    ("no_curated_references", LEVEL_ADVISED,
     "The notes relevant to the unsettled claims do not list sources yet."),
)

_RULE_LEVEL = {rule: level for rule, level, _ in RULES}


@dataclass
class CheckGroup:
    """Unsettled claims that fall under one note section, and where to check."""

    note: str
    heading: str
    claims: List[str]
    references: List[reviewer_notes.Reference]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note": self.note,
            "heading": self.heading,
            "claims": list(self.claims),
            "references": [r.to_dict() for r in self.references],
        }


@dataclass
class Trigger:
    rule: str
    message: str
    items: List[str] = field(default_factory=list)

    @property
    def level(self) -> str:
        return _RULE_LEVEL[self.rule]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "level": self.level,
            "message": self.message,
            "items": list(self.items),
        }


@dataclass
class CheckFurtherAssessment:
    level: str
    triggers: List[Trigger]
    groups: List[CheckGroup]
    further_reading: List[Tuple[str, str, reviewer_notes.Reference]]
    notes_consulted: List[Tuple[str, str]]

    @property
    def headline(self) -> str:
        return HEADLINES[self.level]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "headline": self.headline,
            "rules_version": RULES_VERSION,
            "triggers": [t.to_dict() for t in self.triggers],
            "groups": [g.to_dict() for g in self.groups],
            "further_reading": [
                dict(ref.to_dict(), note=note, heading=heading)
                for note, heading, ref in self.further_reading
            ],
            "notes_consulted": [
                {"note": note, "heading": heading}
                for note, heading in self.notes_consulted
            ],
            "rules": [
                {"rule": rule, "level": level, "when": when}
                for rule, level, when in RULES
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(statement: str) -> str:
    """Case, spacing, quotes and final punctuation only; wording is kept.

    Paraphrases are not merged: saying two sentences mean the same thing is a
    judgement, and this layer makes none.
    """
    text = re.sub(r"[\"'‘’“”]", "", statement or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text.rstrip(" .;:")


def _home_section(passages) -> Optional[Tuple[str, str]]:
    """The retrieved section a claim was judged against most closely."""
    if not passages:
        return None
    best = max(passages, key=lambda p: (p.score or 0.0))
    if not (best.score or 0.0):
        best = passages[0]
    return (best.note, best.heading)


def _dedupe_references(refs):
    seen, out = set(), []
    for ref in refs:
        key = ref.doi.lower() or ref.url or ref.isbn or ref.cite
        if key in seen:
            continue
        seen.add(key)
        out.append(ref)
    return out


def _reference_label(proposed) -> str:
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


# ---------------------------------------------------------------------------
# Assessment
# ---------------------------------------------------------------------------

def assess_check_further(
    result: Any,
    index: reviewer_notes.NotesIndex,
) -> CheckFurtherAssessment:
    """Apply RULES to a checked Academic Chat result.

    ``result`` is an AcademicFirstStageResult: for a reconciled answer, pass
    the final attempt. ``index`` should be the index that supplied the
    guidance, so the references match the sections that were retrieved.
    """
    triggers: List[Trigger] = []
    consistent = academic_methodology.METHODOLOGICAL_STATUS_CONSISTENT
    conflict = academic_methodology.METHODOLOGICAL_STATUS_CONFLICT

    # ---- release ---------------------------------------------------------
    release = result.release
    if not release.safe_to_present:
        reasons = list(release.reasons) or [release.status]
        triggers.append(Trigger(
            "release_blocked",
            "The checks blocked this answer or could not finish checking it.",
            reasons,
        ))

    # ---- collect every methodological judgement, as the release does ------
    assessments = list(result.discovered_claim_assessments or [])
    judgements = []   # (statement, status, passages, contextual)
    for item in result.technical_claims or []:
        method = item.methodological_consistency
        if method is None:
            continue
        if academic_orchestrator.standalone_methodology_is_contextually_superseded(
                item.claim, assessments):
            continue
        judgements.append((item.claim.statement, method.status,
                           list(method.passages), False))
    for item in assessments:
        method = item.contextual_methodological_consistency
        if method is None:
            continue
        judgements.append((item.discovered_claim.claim.statement,
                           method.status, list(method.passages), True))

    # ---- conflicts ---------------------------------------------------------
    conflicts = []
    seen_conflicts = set()
    for statement, status, passages, _ in judgements:
        if status != conflict:
            continue
        key = _normalise(statement)
        if key in seen_conflicts:
            continue
        seen_conflicts.add(key)
        home = _home_section(passages)
        where = f" (see {home[0]} - {home[1]})" if home and home[1] else ""
        conflicts.append(statement + where)
    if conflicts:
        triggers.append(Trigger(
            "notes_conflict",
            "Your notes say something incompatible with part of this answer.",
            conflicts,
        ))

    # ---- references the answer itself proposed -----------------------------
    unconfirmed = []
    for proposal in result.references or []:
        verification = proposal.verification
        status = getattr(verification.crossref_verification, "status", "")
        if status != "verified" or verification.identity_conflict:
            unconfirmed.append(_reference_label(proposal.proposed_reference))
    if unconfirmed:
        triggers.append(Trigger(
            "reference_not_confirmed",
            "The answer cites a source that could not be matched to a "
            "published record, or whose details conflict with it.",
            unconfirmed,
        ))

    # ---- was anything in the notes brought to bear at all? -----------------
    guidance = list(getattr(result.local_guidance, "passages", []) or [])
    if not guidance and not any(p for _, _, p, _ in judgements):
        triggers.append(Trigger(
            "no_guidance",
            "Nothing in your notes addresses this question, so no part of "
            "the answer was checked against them.",
        ))

    if guidance and not judgements:
        triggers.append(Trigger(
            "nothing_checked",
            "Your notes were consulted, but no claim in this answer was "
            "judged against them, so agreement with them is unknown.",
        ))

    # ---- claims the notes do not settle ------------------------------------
    # A statement is settled once any judgement of it is consistent; one
    # judged in conflict is reported above instead. What remains is grouped
    # under the section it was judged against most closely.
    settled = {_normalise(s) for s, st, _, _ in judgements if st == consistent}
    groups: Dict[Tuple[str, str], CheckGroup] = {}
    order: List[Tuple[str, str]] = []
    counted = set()
    for statement, status, passages, _ in judgements:
        key = _normalise(statement)
        if (status == consistent or status == conflict or key in settled
                or key in seen_conflicts or key in counted):
            continue
        counted.add(key)
        home = _home_section(passages) or ("", "")
        if home not in groups:
            groups[home] = CheckGroup(
                note=home[0],
                heading=home[1],
                claims=[],
                references=index.references_for(*home) if home[0] else [],
            )
            order.append(home)
        groups[home].claims.append(statement)
    group_list = [groups[k] for k in order]

    if counted:
        noun = "claim" if len(counted) == 1 else "claims"
        triggers.append(Trigger(
            "not_settled_by_notes",
            f"{len(counted)} {noun} in this answer are neither supported nor "
            "contradicted by your notes.",
            [f"{g.note} - {g.heading}" if g.note else
             "Not close to any section of your notes"
             for g in group_list],
        ))

    # ---- conditions lost when a claim was separated from the answer --------
    unresolved = []
    for item in assessments:
        restriction = item.material_restriction
        if restriction is None or not restriction.material_restriction_omitted:
            continue
        method = item.contextual_methodological_consistency
        if method is not None and method.status == consistent:
            continue
        unresolved.append(item.discovered_claim.claim.statement)
    if unresolved:
        triggers.append(Trigger(
            "condition_not_resolved",
            "A claim was checked without a condition the answer attached to "
            "it, and restoring the condition did not show it consistent with "
            "your notes.",
            unresolved,
        ))

    # ---- somewhere to check -------------------------------------------------
    uncovered = [
        f"{g.note} - {g.heading}" if g.note else
        "Claims not close to any section of your notes"
        for g in group_list if not g.references
    ]
    if uncovered:
        triggers.append(Trigger(
            "no_curated_references",
            "These parts of your notes do not list sources yet, so there is "
            "no curated place to check the claims under them.",
            uncovered,
        ))

    # ---- further reading: the curated sources for what was consulted -------
    consulted: List[Tuple[str, str]] = []
    for p in guidance:
        if (p.note, p.heading) not in consulted:
            consulted.append((p.note, p.heading))
    reading: List[Tuple[str, str, reviewer_notes.Reference]] = []
    seen_reading = set()
    for note, heading in consulted:
        for ref in index.references_for(note, heading):
            key = ref.doi.lower() or ref.url or ref.isbn or ref.cite
            if key in seen_reading:
                continue
            seen_reading.add(key)
            reading.append((note, heading, ref))

    level = LEVEL_SETTLED
    for trigger in triggers:
        if _LEVEL_ORDER[trigger.level] > _LEVEL_ORDER[level]:
            level = trigger.level

    for group in group_list:
        group.references = _dedupe_references(group.references)

    return CheckFurtherAssessment(
        level=level,
        triggers=sorted(triggers, key=lambda t: -_LEVEL_ORDER[t.level]),
        groups=group_list,
        further_reading=reading,
        notes_consulted=consulted,
    )
