"""
One-attempt reconciliation lifecycle for Academic Chat.

This layer composes first-stage generation/checking with bounded correction
extraction, one local revision attempt, and fresh reassessment.

It does not perform generation, verification, or release assessment itself.
The original user question is used only by the supplied first-stage runner.
Reconciliation operates on the retained AcademicDraft and application-owned
checking results.
"""

from dataclasses import dataclass
from typing import Any, Callable

import academic_chat
import academic_orchestrator
import academic_reconciliation


@dataclass
class AcademicReconciliationResult:
    """Audit both attempts while exposing the independently checked final one."""

    initial: academic_orchestrator.AcademicFirstStageResult
    revised: academic_orchestrator.AcademicFirstStageResult | None
    revision_attempted: bool

    @property
    def final(self) -> academic_orchestrator.AcademicFirstStageResult:
        if self.revised is not None:
            return self.revised
        return self.initial


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
    never performs a second revision.
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
    )
