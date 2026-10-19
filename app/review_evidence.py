"""
Typed quantitative evidence for manuscript review.

This module is deliberately upstream of candidate findings and methodological
assessment.  It records what an extracted quantity represents and can expose
deterministic comparison opportunities between identified quantities.

It does NOT decide whether a difference is important, desirable, erroneous,
or methodologically concerning.  Those are semantic review judgements.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .table_evidence import NamedQuantity, TableRecord


class IdentityState(str, Enum):
    """How securely the application has identified a reported quantity."""

    IDENTIFIED = "identified"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ComparabilityState(str, Enum):
    """
    Whether the evidence identities support a comparison opportunity.

    COMPARISON_OPPORTUNITY means that the application has established enough
    shared identity to place the quantities together for later assessment.  It
    does NOT mean that the analyses are methodologically comparable or that a
    numerical difference has substantive meaning.
    """

    COMPARISON_OPPORTUNITY = "comparison_opportunity"
    NOT_COMPARABLE = "not_comparable"
    UNRESOLVED = "unresolved"


class ComparisonRelationship(str, Enum):
    """Structural relationship only; never a methodological verdict."""

    SAME_REPORTED_PARAMETER = "same_reported_parameter"
    SAME_PARAMETER_ACROSS_ANALYSES = "same_parameter_across_analyses"
    SAME_FIT_METRIC_ACROSS_ANALYSES = "same_fit_metric_across_analyses"


@dataclass(frozen=True)
class EvidenceValue:
    """
    One identified quantitative value as reported in manuscript evidence.

    Identity describes how securely the application has identified what the
    source reports. It does not validate that a reported statistical label is
    substantively correct. For example, parameter="SD" means that the value was
    reported under an SD heading; it does not establish that the value is a
    valid standard deviation.
    """

    evidence_id: str
    source_name: str
    source_chunk_id: Optional[int]
    page: Optional[int]
    table_id: Optional[str]

    outcome: Optional[str]
    analysis: Optional[str]
    model: Optional[str]
    parameter: str

    estimate: float
    interval_lower: Optional[float] = None
    interval_upper: Optional[float] = None
    interval_type: Optional[str] = None

    identity_state: IdentityState = IdentityState.IDENTIFIED
    provenance: Optional[str] = None


@dataclass(frozen=True)
class EvidenceComparison:
    """A deterministic opportunity to compare two evidence values."""

    comparison_id: str
    left_evidence_id: str
    right_evidence_id: str

    relationship: Optional[ComparisonRelationship]
    comparability_state: ComparabilityState

    parameter: Optional[str]
    outcome: Optional[str]
    left_analysis: Optional[str]
    right_analysis: Optional[str]

    deterministic_difference: Optional[float]
    reason: str


class EvidenceRelationship(str, Enum):
    """The specific semantic identity relationship being evaluated."""

    ANALYSED_OBSERVATIONS = "analysed_observations"
    MODEL_SPECIFICATION = "model_specification"


class RelationshipState(str, Enum):
    """What the supplied source evidence establishes for a relationship."""

    ESTABLISHED_SAME = "established_same"
    ESTABLISHED_DIFFERENT = "established_different"
    NOT_ESTABLISHED = "not_established"


class RelationshipEvidenceKind(str, Enum):
    """
    Kind of source evidence supplied to the deterministic acceptance gate.

    Only explicit identity or explicit difference can establish a semantic
    relationship. Numerical or structural correspondence remains supporting
    observation and cannot establish semantic identity by itself.
    """

    EXPLICIT_IDENTITY = "explicit_identity"
    EXPLICIT_DIFFERENCE = "explicit_difference"
    NUMERIC_CORRESPONDENCE = "numeric_correspondence"
    STRUCTURAL_CORRESPONDENCE = "structural_correspondence"


@dataclass(frozen=True)
class RelationshipEvidenceItem:
    """One source-grounded observation relevant to a specific relationship."""

    relationship: EvidenceRelationship
    kind: RelationshipEvidenceKind
    description: str
    provenance: Optional[str] = None


@dataclass(frozen=True)
class AcceptedRelationshipEvidence:
    """
    Deterministic result of evaluating source-grounded relationship evidence.

    This object records only what the supplied evidence establishes. It does
    not store or accept an LLM verdict and does not assess methodological
    comparability.
    """

    relationship: EvidenceRelationship
    state: RelationshipState
    evidence: tuple[RelationshipEvidenceItem, ...]
    reason: str


def accept_relationship_evidence(
    relationship: EvidenceRelationship,
    evidence: tuple[RelationshipEvidenceItem, ...],
) -> AcceptedRelationshipEvidence:
    """
    Accept only explicit source evidence as semantic relationship evidence.

    The gate is deliberately asymmetric and fail-closed:

    * explicit identity alone can establish ESTABLISHED_SAME;
    * explicit difference alone can establish ESTABLISHED_DIFFERENT;
    * numerical or structural correspondence cannot establish either state;
    * conflicting explicit identity and difference evidence is unresolved.

    No inference is made from numerical equality, structural similarity,
    labels, model output, or statistical plausibility.
    """

    applicable_evidence = tuple(
        item for item in evidence if item.relationship == relationship
    )
    kinds = {item.kind for item in applicable_evidence}
    has_identity = RelationshipEvidenceKind.EXPLICIT_IDENTITY in kinds
    has_difference = RelationshipEvidenceKind.EXPLICIT_DIFFERENCE in kinds

    if has_identity and has_difference:
        return AcceptedRelationshipEvidence(
            relationship=relationship,
            state=RelationshipState.NOT_ESTABLISHED,
            evidence=applicable_evidence,
            reason=(
                "Explicit identity and explicit difference evidence conflict; "
                "the relationship is not established."
            ),
        )

    if has_identity:
        return AcceptedRelationshipEvidence(
            relationship=relationship,
            state=RelationshipState.ESTABLISHED_SAME,
            evidence=applicable_evidence,
            reason=(
                "The supplied source evidence explicitly establishes identity "
                "for the specified relationship."
            ),
        )

    if has_difference:
        return AcceptedRelationshipEvidence(
            relationship=relationship,
            state=RelationshipState.ESTABLISHED_DIFFERENT,
            evidence=applicable_evidence,
            reason=(
                "The supplied source evidence explicitly establishes a "
                "difference for the specified relationship."
            ),
        )

    return AcceptedRelationshipEvidence(
        relationship=relationship,
        state=RelationshipState.NOT_ESTABLISHED,
        evidence=applicable_evidence,
        reason=(
            "The supplied evidence does not explicitly establish identity or "
            "difference for the specified relationship."
        ),
    )


_DATA_POINT_COUNT_RE = re.compile(
    r"(?<!\d)(\d+)\s+data\s+points?\b",
    flags=re.IGNORECASE,
)


def _explicit_data_point_count(label: Optional[str]) -> Optional[int]:
    """
    Return one explicitly reported '<integer> data point(s)' count.

    The parser fails closed when the label contains no such count or more than
    one such count. Other numbers in the label are ignored.
    """
    if label is None:
        return None

    matches = _DATA_POINT_COUNT_RE.findall(label)
    if len(matches) != 1:
        return None

    return int(matches[0])


def _record_acquisition_provenance(record: TableRecord) -> str:
    """
    Describe acquisition provenance without promoting it to verification.

    Mixed or absent quantity provenance is retained explicitly.
    """
    methods = sorted(
        {
            quantity.acquisition_method.value
            for quantity in record.quantities
        }
    )
    sources = sorted(
        {
            quantity.extraction_source
            for quantity in record.quantities
            if quantity.extraction_source is not None
        }
    )

    method_text = ",".join(methods) if methods else "unavailable"
    source_text = ",".join(sources) if sources else "unavailable"

    return (
        f"source={record.source_name}; page={record.page}; "
        f"table={record.table_evidence_id}; "
        f"acquisition_method={method_text}; "
        f"extraction_source={source_text}"
    )


def explicit_analysed_observation_count_difference(
    left: TableRecord,
    right: TableRecord,
) -> Optional[RelationshipEvidenceItem]:
    """
    Construct explicit difference evidence from reported analysed-data counts.

    This constructor is deliberately asymmetric. Different explicit counts can
    establish evidence that the analysed observations differ. Equal counts do
    not establish identity.

    Records must belong to the same known source table and have the same row
    label after only case/whitespace normalisation. No inference is made from
    numerical results, structural similarity, or model output.
    """
    same_known_table = (
        left.table_evidence_id is not None
        and right.table_evidence_id is not None
        and left.table_evidence_id == right.table_evidence_id
        and left.source_name == right.source_name
    )
    if not same_known_table:
        return None

    left_row = _normalise(left.row_label)
    right_row = _normalise(right.row_label)
    if left_row is None or right_row is None or left_row != right_row:
        return None

    left_count = _explicit_data_point_count(left.section_label)
    right_count = _explicit_data_point_count(right.section_label)

    if left_count is None or right_count is None:
        return None
    if left_count == right_count:
        return None

    provenance = (
        f"left[{_record_acquisition_provenance(left)}]; "
        f"right[{_record_acquisition_provenance(right)}]"
    )

    return RelationshipEvidenceItem(
        relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
        kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
        description=(
            "The source table reports different analysed-data counts for the "
            f"matched row: {left_count} data points versus "
            f"{right_count} data points."
        ),
        provenance=provenance,
    )


_COVARIATE_ANALYSIS_HEADER = "covariate analysis"


def explicit_covariate_analysis_specification_difference(
    left: TableRecord,
    right: TableRecord,
) -> Optional[RelationshipEvidenceItem]:
    """
    Construct explicit model-specification difference evidence from a table
    dimension explicitly labelled 'Covariate Analysis'.

    This is intentionally narrow. Different row labels establish evidence only
    when both records belong to the same known source table and section, both
    preserve the same recognised row-label header, and that header is
    'Covariate Analysis'. No broader meaning is inferred from arbitrary row
    labels or table structure.
    """
    same_known_table = (
        left.table_evidence_id is not None
        and right.table_evidence_id is not None
        and left.table_evidence_id == right.table_evidence_id
        and left.source_name == right.source_name
    )
    if not same_known_table:
        return None

    left_section = _normalise(left.section_label)
    right_section = _normalise(right.section_label)
    if (
        left.section_index != right.section_index
        or left_section is None
        or right_section is None
        or left_section != right_section
    ):
        return None

    left_header = _normalise(left.row_label_header)
    right_header = _normalise(right.row_label_header)
    if (
        left_header != _COVARIATE_ANALYSIS_HEADER
        or right_header != _COVARIATE_ANALYSIS_HEADER
    ):
        return None

    left_row = _normalise(left.row_label)
    right_row = _normalise(right.row_label)
    if left_row is None or right_row is None or left_row == right_row:
        return None

    provenance = (
        f"left[{_record_acquisition_provenance(left)}]; "
        f"right[{_record_acquisition_provenance(right)}]"
    )

    return RelationshipEvidenceItem(
        relationship=EvidenceRelationship.MODEL_SPECIFICATION,
        kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
        description=(
            "The source table reports different entries on the explicitly "
            f"labelled Covariate Analysis dimension: {left.row_label!r} "
            f"versus {right.row_label!r}."
        ),
        provenance=provenance,
    )

_FIT_METRICS = {
    "dic",
    "pd",
    "residual_deviance",
}


def _normalise(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return " ".join(value.strip().casefold().split())


def evidence_value_from_named_quantity(
    quantity: NamedQuantity,
) -> EvidenceValue:
    """
    Promote literal reported table evidence into a typed evidence value.

    The quantity label is retained as the reported parameter identity. A row
    label is promoted to an analysis identity only for the explicitly
    demonstrated ``Covariate Analysis`` dimension. Section labels are not
    promoted to outcomes, and no model identity is inferred.

    IDENTIFIED therefore means that the reported source identity is identified;
    it does not validate the manuscript's statistical terminology or establish
    methodological comparability.
    """
    analysis = (
        quantity.row_label
        if _normalise(quantity.row_label_header) == "covariate analysis"
        else None
    )

    payload = "|".join(
        (
            quantity.source_name,
            str(quantity.page),
            str(quantity.table_evidence_id),
            str(quantity.section_index),
            str(quantity.section_label),
            str(quantity.row_index),
            quantity.row_label,
            str(quantity.row_label_header),
            quantity.quantity_label,
            quantity.raw_value,
            quantity.acquisition_method.value,
            str(quantity.extraction_source),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    provenance_parts = [
        f"acquisition_method={quantity.acquisition_method.value}",
    ]
    if quantity.extraction_source is not None:
        provenance_parts.append(
            f"extraction_source={quantity.extraction_source}"
        )
    if quantity.caption is not None:
        provenance_parts.append(f"caption={quantity.caption}")
    if quantity.section_label is not None:
        provenance_parts.append(
            f"section_label={quantity.section_label}"
        )
    if quantity.row_label_header is not None:
        provenance_parts.append(
            f"row_label_header={quantity.row_label_header}"
        )
    provenance_parts.append(f"row_label={quantity.row_label}")

    return EvidenceValue(
        evidence_id=f"evidence-{digest}",
        source_name=quantity.source_name,
        source_chunk_id=None,
        page=quantity.page,
        table_id=quantity.table_evidence_id,
        outcome=None,
        analysis=analysis,
        model=None,
        parameter=quantity.quantity_label,
        estimate=quantity.central_value,
        interval_lower=quantity.lower_value,
        interval_upper=quantity.upper_value,
        interval_type=None,
        identity_state=IdentityState.IDENTIFIED,
        provenance="; ".join(provenance_parts),
    )


def _comparison_id(left: EvidenceValue, right: EvidenceValue) -> str:
    payload = f"{left.evidence_id}|{right.evidence_id}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"comparison-{digest}"


def compare_evidence_values(
    left: EvidenceValue,
    right: EvidenceValue,
) -> EvidenceComparison:
    """
    Build a conservative deterministic comparison.

    A comparison is offered only when both values have identified quantity
    identities, the parameter matches, and the outcome matches when an outcome
    is supplied.

    This function deliberately does not infer methodological meaning from the
    direction or magnitude of a difference.
    """

    comparison_id = _comparison_id(left, right)

    if (
        left.identity_state is not IdentityState.IDENTIFIED
        or right.identity_state is not IdentityState.IDENTIFIED
    ):
        return EvidenceComparison(
            comparison_id=comparison_id,
            left_evidence_id=left.evidence_id,
            right_evidence_id=right.evidence_id,
            relationship=None,
            comparability_state=ComparabilityState.UNRESOLVED,
            parameter=None,
            outcome=None,
            left_analysis=left.analysis,
            right_analysis=right.analysis,
            deterministic_difference=None,
            reason=(
                "At least one quantity identity is not established; "
                "comparison is withheld."
            ),
        )

    left_parameter = _normalise(left.parameter)
    right_parameter = _normalise(right.parameter)

    if left_parameter != right_parameter:
        return EvidenceComparison(
            comparison_id=comparison_id,
            left_evidence_id=left.evidence_id,
            right_evidence_id=right.evidence_id,
            relationship=None,
            comparability_state=ComparabilityState.NOT_COMPARABLE,
            parameter=None,
            outcome=None,
            left_analysis=left.analysis,
            right_analysis=right.analysis,
            deterministic_difference=None,
            reason="The quantities represent different parameters.",
        )

    left_outcome = _normalise(left.outcome)
    right_outcome = _normalise(right.outcome)

    if (
        left_outcome is not None
        and right_outcome is not None
        and left_outcome != right_outcome
    ):
        return EvidenceComparison(
            comparison_id=comparison_id,
            left_evidence_id=left.evidence_id,
            right_evidence_id=right.evidence_id,
            relationship=None,
            comparability_state=ComparabilityState.NOT_COMPARABLE,
            parameter=left.parameter,
            outcome=None,
            left_analysis=left.analysis,
            right_analysis=right.analysis,
            deterministic_difference=None,
            reason="The quantities refer to different outcomes.",
        )

    # If only one side has an outcome identity, do not silently assume that the
    # other side belongs to the same outcome.
    if (left_outcome is None) != (right_outcome is None):
        return EvidenceComparison(
            comparison_id=comparison_id,
            left_evidence_id=left.evidence_id,
            right_evidence_id=right.evidence_id,
            relationship=None,
            comparability_state=ComparabilityState.UNRESOLVED,
            parameter=left.parameter,
            outcome=left.outcome or right.outcome,
            left_analysis=left.analysis,
            right_analysis=right.analysis,
            deterministic_difference=None,
            reason=(
                "Outcome identity is present for only one quantity; "
                "comparison is withheld."
            ),
        )

    left_analysis = _normalise(left.analysis)
    right_analysis = _normalise(right.analysis)

    if left_analysis is not None and right_analysis is not None:
        relationship = (
            ComparisonRelationship.SAME_FIT_METRIC_ACROSS_ANALYSES
            if left_parameter in _FIT_METRICS
            else ComparisonRelationship.SAME_PARAMETER_ACROSS_ANALYSES
        )
    else:
        relationship = ComparisonRelationship.SAME_REPORTED_PARAMETER

    return EvidenceComparison(
        comparison_id=comparison_id,
        left_evidence_id=left.evidence_id,
        right_evidence_id=right.evidence_id,
        relationship=relationship,
        comparability_state=ComparabilityState.COMPARISON_OPPORTUNITY,
        parameter=left.parameter,
        outcome=left.outcome or right.outcome,
        left_analysis=left.analysis,
        right_analysis=right.analysis,
        deterministic_difference=right.estimate - left.estimate,
        reason=(
            "Both quantities have identified matching reported parameter "
            "identities and no conflicting identified outcome identities. "
            "This establishes a comparison opportunity, not methodological "
            "comparability."
        ),
    )
