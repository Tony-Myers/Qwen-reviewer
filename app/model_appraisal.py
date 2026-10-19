"""
Experimental proposition-bound model appraisal.

This module records and validates what a language model concluded about one
application-owned proposition from one immutable evidence package.

A structurally valid ModelAppraisalResult is model output. It is NOT
deterministic evidence, a verified methodological conclusion, or authority to
modify any application-owned evidence or relationship state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


from app.review_evidence import (
    AcceptedRelationshipEvidence,
    EvidenceComparison,
    EvidenceValue,
)


MAX_PROPOSITION_CHARS = 2000
MAX_RATIONALE_CHARS = 4000
MAX_UNRESOLVED_PREMISES = 20
MAX_UNRESOLVED_PREMISE_CHARS = 1000
MAX_EVIDENCE_REFERENCES = 100


class ModelAppraisalVerdict(str, Enum):
    """Evidence-relative conclusion returned by the model."""

    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class ModelAppraisalParseError(ValueError):
    """Model appraisal output failed structural or reference validation."""


@dataclass(frozen=True)
class ModelAppraisalEvidenceItem:
    """
    One application-owned, model-visible evidence item.

    text is deterministic application rendering, not model-generated prose.
    """

    evidence_id: str
    text: str
    referenced_evidence_ids: tuple[str, ...] = ()


def evidence_item_from_value(
    value: EvidenceValue,
) -> ModelAppraisalEvidenceItem:
    """Render one reported quantitative value without methodological inference."""

    fields = [
        ("Evidence type", "reported quantitative value"),
        ("Source name", value.source_name),
        ("Source chunk ID", value.source_chunk_id),
        ("Page", value.page),
        ("Table ID", value.table_id),
        ("Outcome", value.outcome),
        ("Analysis", value.analysis),
        ("Model", value.model),
        ("Reported parameter", value.parameter),
        ("Estimate", value.estimate),
        ("Interval lower", value.interval_lower),
        ("Interval upper", value.interval_upper),
        ("Interval type", value.interval_type),
        ("Quantity identity state", value.identity_state.value),
        ("Provenance", value.provenance),
    ]
    rendered = "\n".join(
        f"{label}: {_render_appraisal_field(field_value)}"
        for label, field_value in fields
    )
    return ModelAppraisalEvidenceItem(
        evidence_id=value.evidence_id,
        text=rendered,
    )


def evidence_item_from_comparison(
    comparison: EvidenceComparison,
) -> ModelAppraisalEvidenceItem:
    """
    Render one deterministic structural comparison without methodological
    interpretation.
    """

    fields = [
        ("Evidence type", "deterministic structural comparison"),
        ("Left evidence ID", comparison.left_evidence_id),
        ("Right evidence ID", comparison.right_evidence_id),
        (
            "Structural relationship",
            comparison.relationship.value
            if comparison.relationship is not None
            else None,
        ),
        ("Structural comparison state", comparison.comparability_state.value),
        ("Reported parameter", comparison.parameter),
        ("Outcome", comparison.outcome),
        ("Left analysis", comparison.left_analysis),
        ("Right analysis", comparison.right_analysis),
        ("Deterministic difference", comparison.deterministic_difference),
    ]
    rendered = "\n".join(
        f"{label}: {_render_appraisal_field(field_value)}"
        for label, field_value in fields
    )
    return ModelAppraisalEvidenceItem(
        evidence_id=comparison.comparison_id,
        text=rendered,
        referenced_evidence_ids=(
            comparison.left_evidence_id,
            comparison.right_evidence_id,
        ),
    )


@dataclass(frozen=True)
class ModelAppraisalRelationshipBinding:
    """
    Bind one accepted relationship state to the exact ordered evidence pair
    to which it applies at the model-appraisal handoff.

    This binding does not change or reinterpret the deterministic relationship
    state. It prevents a relationship established for one pair from being
    presented to model appraisal as if it applied to another pair.
    """

    left_evidence_id: str
    right_evidence_id: str
    accepted: AcceptedRelationshipEvidence

    def __post_init__(self) -> None:
        if not self.left_evidence_id.strip():
            raise ValueError("left_evidence_id must be non-empty.")
        if not self.right_evidence_id.strip():
            raise ValueError("right_evidence_id must be non-empty.")


def evidence_item_from_relationship(
    binding: ModelAppraisalRelationshipBinding,
) -> ModelAppraisalEvidenceItem:
    """
    Render one pair-bound application-accepted relationship state.

    The deterministic acceptance reason is deliberately not rendered. Source
    observations are represented literally so the model receives the accepted
    state and its application-owned evidential basis without new interpretation.
    """

    accepted = binding.accepted
    source_evidence = [
        {
            "relationship": item.relationship.value,
            "kind": item.kind.value,
            "description": item.description,
            "provenance": item.provenance,
        }
        for item in accepted.evidence
    ]
    identity_payload = json.dumps(
        {
            "left_evidence_id": binding.left_evidence_id,
            "right_evidence_id": binding.right_evidence_id,
            "relationship": accepted.relationship.value,
            "state": accepted.state.value,
            "evidence": source_evidence,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(
        identity_payload.encode("utf-8")
    ).hexdigest()

    lines = [
        "Evidence type: pair-bound accepted relationship state",
        f"Left evidence ID: {binding.left_evidence_id}",
        f"Right evidence ID: {binding.right_evidence_id}",
        f"Relationship: {accepted.relationship.value}",
        f"State: {accepted.state.value}",
    ]
    for index, item in enumerate(accepted.evidence, start=1):
        lines.extend([
            f"Source evidence {index} kind: {item.kind.value}",
            f"Source evidence {index} description: {item.description}",
            (
                f"Source evidence {index} provenance: "
                f"{_render_appraisal_field(item.provenance)}"
            ),
        ])

    return ModelAppraisalEvidenceItem(
        evidence_id=f"relationship-{digest}",
        text="\n".join(lines),
        referenced_evidence_ids=(
            binding.left_evidence_id,
            binding.right_evidence_id,
        ),
    )


def _render_appraisal_field(value: Any) -> str:
    """Render one application field without filling or interpreting absence."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@dataclass(frozen=True)
class ModelAppraisalEvidencePackage:
    """
    Immutable ordered package of application-rendered evidence.

    package_snapshot_id binds the logical package identity and the exact
    ordered evidence IDs and text supplied by the application.
    """

    evidence_package_id: str
    package_snapshot_id: str
    evidence_items: tuple[ModelAppraisalEvidenceItem, ...]


def build_model_appraisal_evidence_package(
    evidence_package_id: str,
    evidence_items: tuple[ModelAppraisalEvidenceItem, ...],
) -> ModelAppraisalEvidencePackage:
    """Validate and bind one exact ordered evidence-package snapshot."""

    _require_nonempty_string(
        evidence_package_id,
        field_name="evidence_package_id",
        max_chars=500,
    )

    if not isinstance(evidence_items, tuple):
        raise ModelAppraisalParseError(
            "evidence_items must be a tuple."
        )

    if not evidence_items:
        raise ModelAppraisalParseError(
            "evidence_items must not be empty."
        )

    if len(evidence_items) > MAX_EVIDENCE_REFERENCES:
        raise ModelAppraisalParseError(
            "evidence_items exceeds the maximum size."
        )

    seen: set[str] = set()
    canonical_items: list[dict[str, Any]] = []

    for item in evidence_items:
        if not isinstance(item, ModelAppraisalEvidenceItem):
            raise ModelAppraisalParseError(
                "evidence_items must contain ModelAppraisalEvidenceItem "
                "objects."
            )

        evidence_id = _require_nonempty_string(
            item.evidence_id,
            field_name="evidence_id",
            max_chars=500,
        )
        text = _require_nonempty_string(
            item.text,
            field_name="evidence text",
            max_chars=20_000,
        )

        if evidence_id in seen:
            raise ModelAppraisalParseError(
                "evidence_items contains duplicate evidence IDs."
            )
        seen.add(evidence_id)

        if not isinstance(item.referenced_evidence_ids, tuple):
            raise ModelAppraisalParseError(
                "referenced_evidence_ids must be a tuple."
            )

        referenced_ids: list[str] = []
        referenced_seen: set[str] = set()
        for referenced_id in item.referenced_evidence_ids:
            validated_reference = _require_nonempty_string(
                referenced_id,
                field_name="referenced evidence ID",
                max_chars=500,
            )
            if validated_reference == evidence_id:
                raise ModelAppraisalParseError(
                    "Evidence item must not reference itself."
                )
            if validated_reference in referenced_seen:
                raise ModelAppraisalParseError(
                    "referenced_evidence_ids contains duplicate evidence IDs."
                )
            referenced_seen.add(validated_reference)
            referenced_ids.append(validated_reference)

        canonical_items.append({
            "evidence_id": evidence_id,
            "text": text,
            "referenced_evidence_ids": referenced_ids,
        })

    for item in evidence_items:
        missing_references = [
            referenced_id
            for referenced_id in item.referenced_evidence_ids
            if referenced_id not in seen
        ]
        if missing_references:
            raise ModelAppraisalParseError(
                "Evidence item references evidence IDs absent from the "
                "evidence package: "
                + ", ".join(missing_references)
            )

    payload = json.dumps(
        {
            "evidence_package_id": evidence_package_id,
            "evidence_items": canonical_items,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    return ModelAppraisalEvidencePackage(
        evidence_package_id=evidence_package_id,
        package_snapshot_id=f"sha256:{digest}",
        evidence_items=evidence_items,
    )


@dataclass(frozen=True)
class ModelAppraisalTarget:
    """
    Immutable application-owned target for one experimental appraisal.

    permitted_evidence_ids is the exact subset of evidence the model may rely
    on for this target. Package membership alone does not grant permission.
    package_snapshot_id binds the target to the evidence-package version used
    for the invocation.
    """

    target_id: str
    proposition: str
    evidence_package_id: str
    package_snapshot_id: str
    permitted_evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class ModelAppraisalResult:
    """
    One structurally valid model response.

    Structural validity means only that the response passed schema, binding,
    bounds, and evidence-reference checks. It does not establish that the
    model verdict or rationale is methodologically correct.
    """

    target_id: str
    evidence_package_id: str
    package_snapshot_id: str
    model_verdict: ModelAppraisalVerdict
    relied_on_evidence_ids: tuple[str, ...]
    bounded_rationale: str
    model_unresolved_premises: tuple[str, ...]


_REQUIRED_FIELDS = {
    "target_id",
    "evidence_package_id",
    "package_snapshot_id",
    "model_verdict",
    "relied_on_evidence_ids",
    "bounded_rationale",
    "model_unresolved_premises",
}


def _require_nonempty_string(
    value: Any,
    *,
    field_name: str,
    max_chars: int,
) -> str:
    if not isinstance(value, str):
        raise ModelAppraisalParseError(
            f"{field_name} must be a string."
        )

    if not value.strip():
        raise ModelAppraisalParseError(
            f"{field_name} must not be empty."
        )

    if len(value) > max_chars:
        raise ModelAppraisalParseError(
            f"{field_name} exceeds the maximum length of {max_chars}."
        )

    return value


def validate_model_appraisal_target(
    target: ModelAppraisalTarget,
) -> None:
    """Fail closed if an application-owned target is malformed."""

    _require_nonempty_string(
        target.target_id,
        field_name="target_id",
        max_chars=500,
    )
    _require_nonempty_string(
        target.proposition,
        field_name="proposition",
        max_chars=MAX_PROPOSITION_CHARS,
    )
    _require_nonempty_string(
        target.evidence_package_id,
        field_name="evidence_package_id",
        max_chars=500,
    )
    _require_nonempty_string(
        target.package_snapshot_id,
        field_name="package_snapshot_id",
        max_chars=500,
    )

    if not isinstance(target.permitted_evidence_ids, tuple):
        raise ModelAppraisalParseError(
            "permitted_evidence_ids must be a tuple."
        )

    if len(target.permitted_evidence_ids) > MAX_EVIDENCE_REFERENCES:
        raise ModelAppraisalParseError(
            "permitted_evidence_ids exceeds the maximum size."
        )

    seen: set[str] = set()
    for evidence_id in target.permitted_evidence_ids:
        _require_nonempty_string(
            evidence_id,
            field_name="permitted evidence ID",
            max_chars=500,
        )
        if evidence_id in seen:
            raise ModelAppraisalParseError(
                "permitted_evidence_ids contains duplicate IDs."
            )
        seen.add(evidence_id)


def _parse_string_list(
    value: Any,
    *,
    field_name: str,
    max_items: int,
    max_item_chars: int,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ModelAppraisalParseError(
            f"{field_name} must be a list."
        )

    if len(value) > max_items:
        raise ModelAppraisalParseError(
            f"{field_name} exceeds the maximum size of {max_items}."
        )

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        text = _require_nonempty_string(
            item,
            field_name=f"{field_name} item",
            max_chars=max_item_chars,
        )
        if text in seen:
            raise ModelAppraisalParseError(
                f"{field_name} contains duplicate items."
            )
        seen.add(text)
        result.append(text)

    return tuple(result)


def parse_model_appraisal_response(
    raw_response: str,
    target: ModelAppraisalTarget,
) -> ModelAppraisalResult:
    """
    Parse and mechanically validate one model appraisal response.

    Invalid output raises ModelAppraisalParseError. In particular, validation
    failure is NOT converted to NOT_ESTABLISHED.

    Successful parsing establishes only that the response is well formed and
    correctly bound to the supplied target. It does not certify the model's
    conclusion or the relevance of permitted evidence it cited.
    """

    validate_model_appraisal_target(target)

    if not isinstance(raw_response, str) or not raw_response.strip():
        raise ModelAppraisalParseError(
            "Model appraisal response is empty or not a string."
        )

    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ModelAppraisalParseError(
            "Model appraisal response is not valid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ModelAppraisalParseError(
            "Model appraisal response must be a JSON object."
        )

    fields = set(payload)
    missing = _REQUIRED_FIELDS - fields
    unexpected = fields - _REQUIRED_FIELDS

    if missing:
        raise ModelAppraisalParseError(
            "Model appraisal response is missing fields: "
            + ", ".join(sorted(missing))
        )

    if unexpected:
        raise ModelAppraisalParseError(
            "Model appraisal response contains unexpected fields: "
            + ", ".join(sorted(unexpected))
        )

    target_id = _require_nonempty_string(
        payload["target_id"],
        field_name="target_id",
        max_chars=500,
    )
    evidence_package_id = _require_nonempty_string(
        payload["evidence_package_id"],
        field_name="evidence_package_id",
        max_chars=500,
    )
    package_snapshot_id = _require_nonempty_string(
        payload["package_snapshot_id"],
        field_name="package_snapshot_id",
        max_chars=500,
    )

    if target_id != target.target_id:
        raise ModelAppraisalParseError(
            "Returned target_id does not match the invocation target."
        )

    if evidence_package_id != target.evidence_package_id:
        raise ModelAppraisalParseError(
            "Returned evidence_package_id does not match the invocation target."
        )

    if package_snapshot_id != target.package_snapshot_id:
        raise ModelAppraisalParseError(
            "Returned package_snapshot_id does not match the invocation target."
        )

    verdict_value = payload["model_verdict"]
    if not isinstance(verdict_value, str):
        raise ModelAppraisalParseError(
            "model_verdict must be a string."
        )

    try:
        model_verdict = ModelAppraisalVerdict(verdict_value)
    except ValueError as exc:
        raise ModelAppraisalParseError(
            "model_verdict must be SUPPORTED, CONTRADICTED, "
            "or NOT_ESTABLISHED."
        ) from exc

    relied_on_evidence_ids = _parse_string_list(
        payload["relied_on_evidence_ids"],
        field_name="relied_on_evidence_ids",
        max_items=MAX_EVIDENCE_REFERENCES,
        max_item_chars=500,
    )

    permitted = set(target.permitted_evidence_ids)
    unpermitted = [
        evidence_id
        for evidence_id in relied_on_evidence_ids
        if evidence_id not in permitted
    ]
    if unpermitted:
        raise ModelAppraisalParseError(
            "Model appraisal references evidence outside the target's "
            "permitted evidence set: "
            + ", ".join(unpermitted)
        )

    bounded_rationale = _require_nonempty_string(
        payload["bounded_rationale"],
        field_name="bounded_rationale",
        max_chars=MAX_RATIONALE_CHARS,
    )

    model_unresolved_premises = _parse_string_list(
        payload["model_unresolved_premises"],
        field_name="model_unresolved_premises",
        max_items=MAX_UNRESOLVED_PREMISES,
        max_item_chars=MAX_UNRESOLVED_PREMISE_CHARS,
    )

    return ModelAppraisalResult(
        target_id=target_id,
        evidence_package_id=evidence_package_id,
        package_snapshot_id=package_snapshot_id,
        model_verdict=model_verdict,
        relied_on_evidence_ids=relied_on_evidence_ids,
        bounded_rationale=bounded_rationale,
        model_unresolved_premises=model_unresolved_premises,
    )
