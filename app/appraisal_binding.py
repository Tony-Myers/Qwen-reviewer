"""Fail-closed binding of model-proposed appraisal questions to evidence.

This module does not interpret natural-language questions and does not establish
methodological validity.  It only binds a model-proposed atomic question to an
exact application-owned quantitative comparison and exact pair-bound
relationship evidence.
"""

from dataclasses import dataclass
from enum import Enum

from app.model_appraisal import (
    ModelAppraisalRelationshipBinding,
    ModelAppraisalTarget,
    validate_model_appraisal_target,
)
from app.review_evidence import (
    ComparabilityState,
    EvidenceComparison,
    EvidenceRelationship,
    EvidenceValue,
)


@dataclass(frozen=True)
class ProposedAppraisalQuestion:
    """One non-authoritative atomic question proposed by a model."""

    candidate_id: str
    question_id: str
    question: str
    source_anchor: str

    def __post_init__(self) -> None:
        for name, value in (
            ("candidate_id", self.candidate_id),
            ("question_id", self.question_id),
            ("question", self.question),
            ("source_anchor", self.source_anchor),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text.")


@dataclass(frozen=True)
class BoundAppraisalQuestion:
    """
    Exact application-owned evidence binding for a proposed question.

    Binding establishes only that these evidence objects belong to the same
    exact quantitative comparison.  It does not establish that the proposed
    question is methodologically correct, answerable, or suitable for review.
    """

    proposed_question: ProposedAppraisalQuestion
    left_value: EvidenceValue
    right_value: EvidenceValue
    comparison: EvidenceComparison
    relationship_bindings: tuple[ModelAppraisalRelationshipBinding, ...]


def _normalise(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.strip().casefold().split())


def bind_appraisal_question(
    proposed_question: ProposedAppraisalQuestion,
    left_value: EvidenceValue,
    right_value: EvidenceValue,
    comparison: EvidenceComparison,
    relationship_bindings: tuple[ModelAppraisalRelationshipBinding, ...] = (),
) -> BoundAppraisalQuestion:
    """
    Bind one proposed question to one exact application-owned evidence pair.

    The operation is deliberately verification-only.  It does not parse the
    question, select evidence, infer semantic equivalence, or create an
    appraisal target.
    """

    if not isinstance(proposed_question, ProposedAppraisalQuestion):
        raise TypeError(
            "proposed_question must be a ProposedAppraisalQuestion."
        )

    if comparison.left_evidence_id != left_value.evidence_id:
        raise ValueError(
            "Comparison left evidence ID does not match left_value."
        )

    if comparison.right_evidence_id != right_value.evidence_id:
        raise ValueError(
            "Comparison right evidence ID does not match right_value."
        )

    if (
        comparison.comparability_state
        is not ComparabilityState.COMPARISON_OPPORTUNITY
    ):
        raise ValueError(
            "Only an application-established comparison opportunity may be "
            "bound for appraisal."
        )

    comparison_parameter = _normalise(comparison.parameter)
    left_parameter = _normalise(left_value.parameter)
    right_parameter = _normalise(right_value.parameter)

    if (
        comparison_parameter is None
        or comparison_parameter != left_parameter
        or comparison_parameter != right_parameter
    ):
        raise ValueError(
            "Comparison parameter does not match both evidence values."
        )

    if (
        _normalise(comparison.left_analysis)
        != _normalise(left_value.analysis)
        or _normalise(comparison.right_analysis)
        != _normalise(right_value.analysis)
    ):
        raise ValueError(
            "Comparison analysis identities do not match evidence values."
        )

    seen_relationships: set[EvidenceRelationship] = set()

    for binding in relationship_bindings:
        if not isinstance(binding, ModelAppraisalRelationshipBinding):
            raise TypeError(
                "relationship_bindings must contain "
                "ModelAppraisalRelationshipBinding objects."
            )

        if binding.left_evidence_id != left_value.evidence_id:
            raise ValueError(
                "Relationship binding left evidence ID does not match "
                "left_value."
            )

        if binding.right_evidence_id != right_value.evidence_id:
            raise ValueError(
                "Relationship binding right evidence ID does not match "
                "right_value."
            )

        relationship = binding.accepted.relationship
        if relationship in seen_relationships:
            raise ValueError(
                "Duplicate relationship type for the same evidence pair."
            )
        seen_relationships.add(relationship)

    return BoundAppraisalQuestion(
        proposed_question=proposed_question,
        left_value=left_value,
        right_value=right_value,
        comparison=comparison,
        relationship_bindings=relationship_bindings,
    )


class ReferentBindingOrigin(str, Enum):
    """Provenance of one local, non-authoritative referent proposal."""

    LITERAL = "literal"
    MODEL_PROPOSED = "model_proposed"
    MANUAL = "manual"


@dataclass(frozen=True)
class ProposedReferentBinding:
    """
    One local proposed interpretation of text in an atomic question.

    referenced_ids must come from the trace's permitted application-owned
    scope. Their presence here does not establish that the interpretation is
    semantically correct and does not create a global alias or identity.
    """

    expression: str
    referenced_ids: tuple[str, ...]
    origin: ReferentBindingOrigin

    def __post_init__(self) -> None:
        if not isinstance(self.expression, str) or not self.expression.strip():
            raise ValueError("expression must be non-empty text.")
        if not self.referenced_ids:
            raise ValueError("referenced_ids must not be empty.")
        if len(set(self.referenced_ids)) != len(self.referenced_ids):
            raise ValueError("referenced_ids must not contain duplicates.")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in self.referenced_ids
        ):
            raise ValueError("referenced_ids must contain non-empty text.")
        if not isinstance(self.origin, ReferentBindingOrigin):
            raise TypeError("origin must be a ReferentBindingOrigin.")


class ReferentAcceptanceState(str, Enum):
    """Application decision about one exact proposed local referent binding."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ReferentBindingDecision:
    """
    Application decision about one exact proposed local referent binding.

    Acceptance is local to the atomic question. It does not create a global
    alias, establish methodological comparability, or establish that the
    question is suitable for appraisal.
    """

    proposed_binding: ProposedReferentBinding
    state: ReferentAcceptanceState
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.proposed_binding, ProposedReferentBinding):
            raise TypeError(
                "proposed_binding must be a ProposedReferentBinding."
            )
        if not isinstance(self.state, ReferentAcceptanceState):
            raise TypeError("state must be a ReferentAcceptanceState.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty text.")


@dataclass(frozen=True)
class UnresolvedQuestionDependency:
    """One expression or premise that currently blocks complete grounding."""

    expression: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.expression, str) or not self.expression.strip():
            raise ValueError("expression must be non-empty text.")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("reason must be non-empty text.")


@dataclass(frozen=True)
class AtomicQuestionEvidenceTrace:
    """
    Observational provenance trace for one model-proposed atomic question.

    The trace records model-proposed discovery provenance, permitted
    application-owned scope, local referent proposals and unresolved
    dependencies. candidate_quantity_labels are provenance from discovery, not
    application-owned evidence identities and cannot themselves be referent
    targets. The trace does not establish that proposed bindings are
    semantically correct, that grounding is complete, or that the question is
    suitable for promotion to ModelAppraisalTarget.
    """

    proposed_question: ProposedAppraisalQuestion
    permitted_record_ids: tuple[str, ...]
    candidate_quantity_labels: tuple[str, ...]
    permitted_evidence_ids: tuple[str, ...]
    referent_bindings: tuple[ProposedReferentBinding, ...] = ()
    unresolved_dependencies: tuple[UnresolvedQuestionDependency, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.proposed_question, ProposedAppraisalQuestion):
            raise TypeError(
                "proposed_question must be a ProposedAppraisalQuestion."
            )

        for name, values in (
            ("permitted_record_ids", self.permitted_record_ids),
            ("candidate_quantity_labels", self.candidate_quantity_labels),
            ("permitted_evidence_ids", self.permitted_evidence_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates.")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in values
            ):
                raise ValueError(f"{name} must contain non-empty text.")

        permitted = set(self.permitted_record_ids) | set(
            self.permitted_evidence_ids
        )

        seen_expressions: set[str] = set()
        for binding in self.referent_bindings:
            if not isinstance(binding, ProposedReferentBinding):
                raise TypeError(
                    "referent_bindings must contain "
                    "ProposedReferentBinding objects."
                )
            if any(
                reference not in permitted
                for reference in binding.referenced_ids
            ):
                raise ValueError(
                    "Referent binding contains an ID outside permitted scope."
                )

            normalised_expression = _normalise(binding.expression)
            if normalised_expression in seen_expressions:
                raise ValueError(
                    "Duplicate referent binding expression in one trace."
                )
            seen_expressions.add(normalised_expression)

        for dependency in self.unresolved_dependencies:
            if not isinstance(dependency, UnresolvedQuestionDependency):
                raise TypeError(
                    "unresolved_dependencies must contain "
                    "UnresolvedQuestionDependency objects."
                )


class PromotionDecision(str, Enum):
    """Application decision about promotion of one exact target construction."""

    PROMOTED = "promoted"
    WITHHELD = "withheld"


@dataclass(frozen=True)
class AppraisalTargetConstruction:
    """
    Application-owned construction decision for one proposed appraisal target.

    This record preserves the exact observational trace, interpretation-bearing
    binding decisions, subject scope, evidence selection, package snapshot,
    proposition, and promotion provenance.

    PROMOTED means only that the application has accepted this exact
    construction as sufficiently specified for bounded appraisal. It does not
    establish that the proposition is true, that methodological comparability
    exists, or that the selected interpretation is a source fact.
    """

    trace: AtomicQuestionEvidenceTrace
    relied_on_binding_decisions: tuple[ReferentBindingDecision, ...]
    proposition: str
    selected_record_ids: tuple[str, ...]
    selected_evidence_ids: tuple[str, ...]
    evidence_package_id: str
    package_snapshot_id: str
    scope_reason: str
    decision: PromotionDecision
    decision_maker: str
    decision_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.trace, AtomicQuestionEvidenceTrace):
            raise TypeError("trace must be an AtomicQuestionEvidenceTrace.")

        for name, values in (
            ("selected_record_ids", self.selected_record_ids),
            ("selected_evidence_ids", self.selected_evidence_ids),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple.")
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates.")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in values
            ):
                raise ValueError(f"{name} must contain non-empty text.")

        if any(
            record_id not in self.trace.permitted_record_ids
            for record_id in self.selected_record_ids
        ):
            raise ValueError(
                "selected_record_ids contains an ID outside trace scope."
            )

        if any(
            evidence_id not in self.trace.permitted_evidence_ids
            for evidence_id in self.selected_evidence_ids
        ):
            raise ValueError(
                "selected_evidence_ids contains an ID outside trace scope."
            )

        if not isinstance(self.relied_on_binding_decisions, tuple):
            raise TypeError("relied_on_binding_decisions must be a tuple.")

        trace_bindings = set(self.trace.referent_bindings)
        seen_bindings: set[ProposedReferentBinding] = set()

        for binding_decision in self.relied_on_binding_decisions:
            if not isinstance(binding_decision, ReferentBindingDecision):
                raise TypeError(
                    "relied_on_binding_decisions must contain "
                    "ReferentBindingDecision objects."
                )

            proposed_binding = binding_decision.proposed_binding
            if proposed_binding not in trace_bindings:
                raise ValueError(
                    "Relied-on binding decision refers to a proposal absent "
                    "from the trace."
                )
            if proposed_binding in seen_bindings:
                raise ValueError(
                    "Duplicate decision for one relied-on referent binding."
                )
            seen_bindings.add(proposed_binding)

            if (
                self.decision is PromotionDecision.PROMOTED
                and binding_decision.state
                is not ReferentAcceptanceState.ACCEPTED
            ):
                raise ValueError(
                    "PROMOTED construction cannot rely on a referent binding "
                    "that is not ACCEPTED."
                )

        for name, value in (
            ("proposition", self.proposition),
            ("evidence_package_id", self.evidence_package_id),
            ("package_snapshot_id", self.package_snapshot_id),
            ("scope_reason", self.scope_reason),
            ("decision_maker", self.decision_maker),
            ("decision_reason", self.decision_reason),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text.")

        if not isinstance(self.decision, PromotionDecision):
            raise TypeError("decision must be a PromotionDecision.")


def model_appraisal_target_from_construction(
    target_id: str,
    construction: AppraisalTargetConstruction,
) -> ModelAppraisalTarget:
    """
    Create a structurally valid appraisal target from an approved construction.

    This is a copying boundary only. It does not reinterpret the proposition,
    evidence selection, package identity, or package snapshot. A WITHHELD
    construction cannot produce an appraisal target.
    """

    if not isinstance(construction, AppraisalTargetConstruction):
        raise TypeError(
            "construction must be an AppraisalTargetConstruction."
        )

    if construction.decision is not PromotionDecision.PROMOTED:
        raise ValueError(
            "Only a PROMOTED construction can produce a ModelAppraisalTarget."
        )

    target = ModelAppraisalTarget(
        target_id=target_id,
        proposition=construction.proposition,
        evidence_package_id=construction.evidence_package_id,
        package_snapshot_id=construction.package_snapshot_id,
        permitted_evidence_ids=construction.selected_evidence_ids,
    )
    validate_model_appraisal_target(target)
    return target
