import json
import unittest

from app.model_appraisal import (
    build_model_appraisal_evidence_package,
    evidence_item_from_comparison,
    evidence_item_from_relationship,
    evidence_item_from_value,
    ModelAppraisalEvidenceItem,
    ModelAppraisalRelationshipBinding,
    ModelAppraisalParseError,
    ModelAppraisalResult,
    ModelAppraisalTarget,
    ModelAppraisalVerdict,
    parse_model_appraisal_response,
)


from app.review_evidence import (
    AcceptedRelationshipEvidence,
    ComparabilityState,
    ComparisonRelationship,
    EvidenceComparison,
    EvidenceRelationship,
    EvidenceValue,
    IdentityState,
    RelationshipEvidenceItem,
    RelationshipEvidenceKind,
    RelationshipState,
)


class ModelAppraisalTests(unittest.TestCase):

    def setUp(self):
        self.target = ModelAppraisalTarget(
            target_id="target-s9-dic-age",
            proposition=(
                "The reported DIC difference establishes that adding age "
                "worsened relative model fit."
            ),
            evidence_package_id="package-s9",
            package_snapshot_id="sha256-example-snapshot",
            permitted_evidence_ids=(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                "relationship-model-specification",
                "relationship-analysed-observations",
            ),
        )

    def response(self, **changes):
        payload = {
            "target_id": self.target.target_id,
            "evidence_package_id": self.target.evidence_package_id,
            "package_snapshot_id": self.target.package_snapshot_id,
            "model_verdict": "NOT_ESTABLISHED",
            "relied_on_evidence_ids": [
                "evidence-unadjusted-dic",
                "evidence-age-dic",
            ],
            "bounded_rationale": (
                "The reported DIC values differ, but methodological "
                "comparability is not established."
            ),
            "model_unresolved_premises": [
                "Methodological comparability is not established."
            ],
        }
        payload.update(changes)
        return json.dumps(payload)

    def assert_invalid(self, raw):
        with self.assertRaises(ModelAppraisalParseError):
            parse_model_appraisal_response(raw, self.target)

    def test_valid_response(self):
        result = parse_model_appraisal_response(
            self.response(),
            self.target,
        )
        self.assertIsInstance(result, ModelAppraisalResult)
        self.assertEqual(
            result.model_verdict,
            ModelAppraisalVerdict.NOT_ESTABLISHED,
        )

    def test_empty_evidence_references_allowed(self):
        result = parse_model_appraisal_response(
            self.response(relied_on_evidence_ids=[]),
            self.target,
        )
        self.assertEqual(result.relied_on_evidence_ids, ())

    def test_unpermitted_evidence_fails_closed(self):
        self.assert_invalid(
            self.response(
                relied_on_evidence_ids=["evidence-from-another-pair"]
            )
        )

    def test_wrong_target_binding_fails_closed(self):
        self.assert_invalid(
            self.response(target_id="different-target")
        )

    def test_wrong_package_binding_fails_closed(self):
        self.assert_invalid(
            self.response(evidence_package_id="different-package")
        )

    def test_wrong_snapshot_binding_fails_closed(self):
        self.assert_invalid(
            self.response(package_snapshot_id="different-snapshot")
        )

    def test_unknown_verdict_fails_closed(self):
        self.assert_invalid(
            self.response(model_verdict="PROBABLY_SUPPORTED")
        )

    def test_unexpected_field_fails_closed(self):
        self.assert_invalid(self.response(accepted=True))

    def test_missing_field_fails_closed(self):
        payload = json.loads(self.response())
        del payload["bounded_rationale"]
        self.assert_invalid(json.dumps(payload))

    def test_malformed_json_is_validation_failure(self):
        self.assert_invalid(
            '{"model_verdict": "NOT_ESTABLISHED"'
        )

    def test_oversized_rationale_fails_closed(self):
        self.assert_invalid(
            self.response(bounded_rationale="x" * 4001)
        )

    def test_duplicate_evidence_references_fail_closed(self):
        self.assert_invalid(
            self.response(
                relied_on_evidence_ids=[
                    "evidence-age-dic",
                    "evidence-age-dic",
                ]
            )
        )



class ModelAppraisalEvidencePackageTests(unittest.TestCase):

    def items(self):
        return (
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-a",
                text="Reported DIC: 217.901.",
            ),
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-b",
                text="Reported DIC: 245.273.",
            ),
        )

    def test_snapshot_is_deterministic(self):
        first = build_model_appraisal_evidence_package(
            "package-s9",
            self.items(),
        )
        second = build_model_appraisal_evidence_package(
            "package-s9",
            self.items(),
        )
        self.assertEqual(first.package_snapshot_id, second.package_snapshot_id)
        self.assertTrue(first.package_snapshot_id.startswith("sha256:"))
        self.assertEqual(len(first.package_snapshot_id), 71)

    def test_changed_text_changes_snapshot(self):
        first = build_model_appraisal_evidence_package(
            "package-s9",
            self.items(),
        )
        changed = (
            self.items()[0],
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-b",
                text="Reported DIC: 245.274.",
            ),
        )
        second = build_model_appraisal_evidence_package(
            "package-s9",
            changed,
        )
        self.assertNotEqual(
            first.package_snapshot_id,
            second.package_snapshot_id,
        )

    def test_changed_order_changes_snapshot(self):
        first = build_model_appraisal_evidence_package(
            "package-s9",
            self.items(),
        )
        second = build_model_appraisal_evidence_package(
            "package-s9",
            tuple(reversed(self.items())),
        )
        self.assertNotEqual(
            first.package_snapshot_id,
            second.package_snapshot_id,
        )

    def test_changed_package_identity_changes_snapshot(self):
        first = build_model_appraisal_evidence_package(
            "package-s9",
            self.items(),
        )
        second = build_model_appraisal_evidence_package(
            "package-other",
            self.items(),
        )
        self.assertNotEqual(
            first.package_snapshot_id,
            second.package_snapshot_id,
        )

    def test_duplicate_evidence_ids_are_rejected(self):
        duplicate = (
            ModelAppraisalEvidenceItem("evidence-a", "First."),
            ModelAppraisalEvidenceItem("evidence-a", "Second."),
        )
        with self.assertRaises(ModelAppraisalParseError):
            build_model_appraisal_evidence_package(
                "package-s9",
                duplicate,
            )

    def test_dangling_evidence_reference_is_rejected(self):
        items = (
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-a",
                text="Derived evidence.",
                referenced_evidence_ids=("evidence-missing",),
            ),
        )
        with self.assertRaises(ModelAppraisalParseError):
            build_model_appraisal_evidence_package(
                "package-s9",
                items,
            )

    def test_self_reference_is_rejected(self):
        items = (
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-a",
                text="Self-referencing evidence.",
                referenced_evidence_ids=("evidence-a",),
            ),
        )
        with self.assertRaises(ModelAppraisalParseError):
            build_model_appraisal_evidence_package(
                "package-s9",
                items,
            )

    def test_changed_structured_references_change_snapshot(self):
        base_items = (
            ModelAppraisalEvidenceItem("evidence-a", "Evidence A."),
            ModelAppraisalEvidenceItem("evidence-b", "Evidence B."),
            ModelAppraisalEvidenceItem("evidence-c", "Evidence C."),
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-derived",
                text="Identical rendered derived evidence.",
                referenced_evidence_ids=("evidence-a", "evidence-b"),
            ),
        )
        changed_items = (
            ModelAppraisalEvidenceItem("evidence-a", "Evidence A."),
            ModelAppraisalEvidenceItem("evidence-b", "Evidence B."),
            ModelAppraisalEvidenceItem("evidence-c", "Evidence C."),
            ModelAppraisalEvidenceItem(
                evidence_id="evidence-derived",
                text="Identical rendered derived evidence.",
                referenced_evidence_ids=("evidence-a", "evidence-c"),
            ),
        )

        first = build_model_appraisal_evidence_package(
            "package-s9",
            base_items,
        )
        second = build_model_appraisal_evidence_package(
            "package-s9",
            changed_items,
        )

        self.assertNotEqual(
            first.package_snapshot_id,
            second.package_snapshot_id,
        )

    def test_empty_package_is_rejected(self):
        with self.assertRaises(ModelAppraisalParseError):
            build_model_appraisal_evidence_package(
                "package-s9",
                (),
            )


class ModelAppraisalEvidenceRendererTests(unittest.TestCase):

    def value(self, **changes):
        values = {
            "evidence_id": "value-s9-unadjusted",
            "source_name": "supplement.pdf",
            "source_chunk_id": 29,
            "page": 66,
            "table_id": "table-s9",
            "outcome": None,
            "analysis": "Unadjusted",
            "model": None,
            "parameter": "DIC",
            "estimate": 217.901,
            "identity_state": IdentityState.IDENTIFIED,
            "provenance": "vision structured table observation",
        }
        values.update(changes)
        return EvidenceValue(**values)

    def comparison(self):
        return EvidenceComparison(
            comparison_id="comparison-s9-dic",
            left_evidence_id="value-s9-unadjusted",
            right_evidence_id="value-s9-age",
            relationship=ComparisonRelationship.SAME_FIT_METRIC_ACROSS_ANALYSES,
            comparability_state=ComparabilityState.COMPARISON_OPPORTUNITY,
            parameter="DIC",
            outcome=None,
            left_analysis="Unadjusted",
            right_analysis="Age",
            deterministic_difference=27.372,
            reason=(
                "This establishes a comparison opportunity, not "
                "methodological comparability."
            ),
        )

    def relationship(self, description="Rows have different covariate labels."):
        source = RelationshipEvidenceItem(
            relationship=EvidenceRelationship.MODEL_SPECIFICATION,
            kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
            description=description,
            provenance="Table S9",
        )
        return AcceptedRelationshipEvidence(
            relationship=EvidenceRelationship.MODEL_SPECIFICATION,
            state=RelationshipState.ESTABLISHED_DIFFERENT,
            evidence=(source,),
            reason="Deterministic acceptance explanation.",
        )

    def test_value_renderer_preserves_reported_identity(self):
        item = evidence_item_from_value(self.value())
        self.assertEqual(item.evidence_id, "value-s9-unadjusted")
        self.assertIn("Reported parameter: DIC", item.text)
        self.assertIn("Analysis: Unadjusted", item.text)
        self.assertIn("Estimate: 217.901", item.text)
        self.assertIn("Quantity identity state: identified", item.text)

    def test_value_renderer_does_not_validate_reported_label(self):
        item = evidence_item_from_value(
            self.value(
                evidence_id="value-negative-sd",
                parameter="SD",
                estimate=-10.28,
            )
        )
        self.assertIn("Reported parameter: SD", item.text)
        self.assertIn("Estimate: -10.28", item.text)
        self.assertNotIn("valid standard deviation", item.text.lower())
        self.assertNotIn("invalid standard deviation", item.text.lower())

    def test_comparison_renderer_preserves_structural_boundary(self):
        item = evidence_item_from_comparison(self.comparison())
        self.assertEqual(item.evidence_id, "comparison-s9-dic")
        self.assertIn(
            "Structural relationship: same_fit_metric_across_analyses",
            item.text,
        )
        self.assertIn(
            "Structural comparison state: comparison_opportunity",
            item.text,
        )
        self.assertIn("Deterministic difference: 27.372", item.text)
        self.assertNotIn("methodologically comparable", item.text.lower())
        self.assertNotIn("worse fit", item.text.lower())

    def test_relationship_renderer_preserves_accepted_state(self):
        item = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                self.relationship(),
            )
        )
        self.assertTrue(item.evidence_id.startswith("relationship-"))
        self.assertIn("Relationship: model_specification", item.text)
        self.assertIn("State: established_different", item.text)
        self.assertIn(
            "Source evidence 1 kind: explicit_difference",
            item.text,
        )
        self.assertIn(
            "Source evidence 1 description: "
            "Rows have different covariate labels.",
            item.text,
        )

    def test_relationship_reason_is_not_model_visible(self):
        item = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                self.relationship(),
            )
        )
        self.assertNotIn(
            "Deterministic acceptance explanation.",
            item.text,
        )

    def test_relationship_id_changes_with_evidential_basis(self):
        first = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                self.relationship("First explicit distinction."),
            )
        )
        second = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                self.relationship("Second explicit distinction."),
            )
        )
        self.assertNotEqual(first.evidence_id, second.evidence_id)

    def test_relationship_id_does_not_depend_on_reason_wording(self):
        accepted = self.relationship()
        changed_reason = AcceptedRelationshipEvidence(
            relationship=accepted.relationship,
            state=accepted.state,
            evidence=accepted.evidence,
            reason="Reworded deterministic explanation only.",
        )
        first = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                accepted,
            )
        )
        second = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-unadjusted-dic",
                "evidence-age-dic",
                changed_reason,
            )
        )
        self.assertEqual(first.evidence_id, second.evidence_id)
        self.assertEqual(first.text, second.text)


    def test_relationship_renderer_exposes_exact_pair_binding(self):
        item = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-A",
                "evidence-B",
                self.relationship(),
            )
        )
        self.assertIn("Left evidence ID: evidence-A", item.text)
        self.assertIn("Right evidence ID: evidence-B", item.text)

    def test_comparison_renderer_records_exact_evidence_references(self):
        item = evidence_item_from_comparison(self.comparison())
        self.assertEqual(
            item.referenced_evidence_ids,
            ("value-s9-unadjusted", "value-s9-age"),
        )

    def test_relationship_renderer_records_exact_pair_references(self):
        item = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-A",
                "evidence-B",
                self.relationship(),
            )
        )
        self.assertEqual(
            item.referenced_evidence_ids,
            ("evidence-A", "evidence-B"),
        )

    def test_relationship_id_changes_when_bound_pair_changes(self):
        accepted = self.relationship()
        ab = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-A",
                "evidence-B",
                accepted,
            )
        )
        ac = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-A",
                "evidence-C",
                accepted,
            )
        )
        self.assertNotEqual(ab.evidence_id, ac.evidence_id)

    def test_relationship_pair_binding_is_ordered(self):
        accepted = self.relationship()
        ab = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-A",
                "evidence-B",
                accepted,
            )
        )
        ba = evidence_item_from_relationship(
            ModelAppraisalRelationshipBinding(
                "evidence-B",
                "evidence-A",
                accepted,
            )
        )
        self.assertNotEqual(ab.evidence_id, ba.evidence_id)

    def test_relationship_binding_rejects_empty_pair_ids(self):
        with self.assertRaises(ValueError):
            ModelAppraisalRelationshipBinding(
                "",
                "evidence-B",
                self.relationship(),
            )
        with self.assertRaises(ValueError):
            ModelAppraisalRelationshipBinding(
                "evidence-A",
                "   ",
                self.relationship(),
            )

if __name__ == "__main__":
    unittest.main()
