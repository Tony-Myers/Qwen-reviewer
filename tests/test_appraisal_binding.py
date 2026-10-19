import unittest

from app.appraisal_binding import (
    AppraisalTargetConstruction,
    AtomicQuestionEvidenceTrace,
    PromotionDecision,
    ProposedAppraisalQuestion,
    ProposedReferentBinding,
    ReferentAcceptanceState,
    ReferentBindingDecision,
    ReferentBindingOrigin,
    UnresolvedQuestionDependency,
    bind_appraisal_question,
    model_appraisal_target_from_construction,
)
from app.model_appraisal import ModelAppraisalRelationshipBinding
from app.review_evidence import (
    AcceptedRelationshipEvidence,
    ComparabilityState,
    ComparisonRelationship,
    EvidenceComparison,
    EvidenceRelationship,
    EvidenceValue,
    RelationshipState,
)


class AppraisalBindingTests(unittest.TestCase):

    def setUp(self):
        self.question = ProposedAppraisalQuestion(
            candidate_id="candidate-4",
            question_id="question-2",
            question=(
                "Is the resulting DIC difference between unadjusted and "
                "adjusted models interpretable as model fit improvement?"
            ),
            source_anchor=(
                "is the resulting DIC difference between unadjusted and "
                "adjusted models interpretable as model fit improvement?"
            ),
        )

        self.left = EvidenceValue(
            evidence_id="evidence-unadjusted-dic",
            source_name="benchmark.pdf",
            source_chunk_id=None,
            page=66,
            table_id="S9",
            outcome=None,
            analysis="Unadjusted",
            model=None,
            parameter="DIC",
            estimate=217.901,
        )

        self.right = EvidenceValue(
            evidence_id="evidence-age-dic",
            source_name="benchmark.pdf",
            source_chunk_id=None,
            page=66,
            table_id="S9",
            outcome=None,
            analysis="Age",
            model=None,
            parameter="DIC",
            estimate=245.273,
        )

        self.comparison = EvidenceComparison(
            comparison_id="comparison-dic",
            left_evidence_id=self.left.evidence_id,
            right_evidence_id=self.right.evidence_id,
            relationship=(
                ComparisonRelationship.SAME_FIT_METRIC_ACROSS_ANALYSES
            ),
            comparability_state=ComparabilityState.COMPARISON_OPPORTUNITY,
            parameter="DIC",
            outcome=None,
            left_analysis="Unadjusted",
            right_analysis="Age",
            deterministic_difference=27.372,
            reason=(
                "Comparison opportunity only; methodological comparability "
                "is not established."
            ),
        )

    def accepted(self, relationship, state):
        return AcceptedRelationshipEvidence(
            relationship=relationship,
            state=state,
            evidence=(),
            reason="synthetic deterministic test state",
        )

    def binding(self, relationship, state, left_id=None, right_id=None):
        return ModelAppraisalRelationshipBinding(
            left_evidence_id=left_id or self.left.evidence_id,
            right_evidence_id=right_id or self.right.evidence_id,
            accepted=self.accepted(relationship, state),
        )

    def test_valid_exact_pair_binding_succeeds(self):
        model_spec = self.binding(
            EvidenceRelationship.MODEL_SPECIFICATION,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )
        observations = self.binding(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            RelationshipState.NOT_ESTABLISHED,
        )

        bound = bind_appraisal_question(
            self.question,
            self.left,
            self.right,
            self.comparison,
            (model_spec, observations),
        )

        self.assertEqual(bound.left_value.evidence_id, self.left.evidence_id)
        self.assertEqual(bound.right_value.evidence_id, self.right.evidence_id)
        self.assertEqual(
            bound.comparison.comparability_state,
            ComparabilityState.COMPARISON_OPPORTUNITY,
        )
        self.assertEqual(
            bound.relationship_bindings[0].accepted.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )
        self.assertEqual(
            bound.relationship_bindings[1].accepted.state,
            RelationshipState.NOT_ESTABLISHED,
        )

    def test_dic_comparison_cannot_bind_pd_value(self):
        pd_value = EvidenceValue(
            evidence_id=self.right.evidence_id,
            source_name="benchmark.pdf",
            source_chunk_id=None,
            page=66,
            table_id="S9",
            outcome=None,
            analysis="Age",
            model=None,
            parameter="pD",
            estimate=113.593,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Comparison parameter does not match both evidence values",
        ):
            bind_appraisal_question(
                self.question,
                self.left,
                pd_value,
                self.comparison,
            )

    def test_reversed_pair_fails(self):
        with self.assertRaisesRegex(
            ValueError,
            "Comparison left evidence ID does not match left_value",
        ):
            bind_appraisal_question(
                self.question,
                self.right,
                self.left,
                self.comparison,
            )

    def test_relationship_from_another_pair_fails(self):
        borrowed = self.binding(
            EvidenceRelationship.MODEL_SPECIFICATION,
            RelationshipState.ESTABLISHED_DIFFERENT,
            left_id="evidence-other-left",
            right_id="evidence-other-right",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Relationship binding left evidence ID does not match left_value",
        ):
            bind_appraisal_question(
                self.question,
                self.left,
                self.right,
                self.comparison,
                (borrowed,),
            )

    def test_non_opportunity_comparison_fails(self):
        withheld = EvidenceComparison(
            comparison_id="comparison-withheld",
            left_evidence_id=self.left.evidence_id,
            right_evidence_id=self.right.evidence_id,
            relationship=None,
            comparability_state=ComparabilityState.UNRESOLVED,
            parameter="DIC",
            outcome=None,
            left_analysis="Unadjusted",
            right_analysis="Age",
            deterministic_difference=None,
            reason="Comparison withheld.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Only an application-established comparison opportunity",
        ):
            bind_appraisal_question(
                self.question,
                self.left,
                self.right,
                withheld,
            )

    def test_comparison_analysis_identity_mismatch_fails(self):
        inconsistent = EvidenceComparison(
            comparison_id="comparison-inconsistent-analysis",
            left_evidence_id=self.left.evidence_id,
            right_evidence_id=self.right.evidence_id,
            relationship=(
                ComparisonRelationship.SAME_FIT_METRIC_ACROSS_ANALYSES
            ),
            comparability_state=ComparabilityState.COMPARISON_OPPORTUNITY,
            parameter="DIC",
            outcome=None,
            left_analysis="Publication date",
            right_analysis="Years of education",
            deterministic_difference=27.372,
            reason="Synthetic internally inconsistent comparison.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Comparison analysis identities do not match evidence values",
        ):
            bind_appraisal_question(
                self.question,
                self.left,
                self.right,
                inconsistent,
            )

    def test_duplicate_relationship_type_fails(self):
        first = self.binding(
            EvidenceRelationship.MODEL_SPECIFICATION,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )
        second = self.binding(
            EvidenceRelationship.MODEL_SPECIFICATION,
            RelationshipState.NOT_ESTABLISHED,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate relationship type",
        ):
            bind_appraisal_question(
                self.question,
                self.left,
                self.right,
                self.comparison,
                (first, second),
            )

    def test_partial_trace_with_unresolved_dependencies_is_valid(self):
        trace = AtomicQuestionEvidenceTrace(
            proposed_question=self.question,
            permitted_record_ids=("record-01", "record-02"),
            candidate_quantity_labels=("DIC", "pD", "Residual Deviance"),
            permitted_evidence_ids=(
                self.left.evidence_id,
                self.right.evidence_id,
            ),
            referent_bindings=(
                ProposedReferentBinding(
                    expression="DIC",
                    referenced_ids=(
                        self.left.evidence_id,
                        self.right.evidence_id,
                    ),
                    origin=ReferentBindingOrigin.LITERAL,
                ),
            ),
            unresolved_dependencies=(
                UnresolvedQuestionDependency(
                    expression="adjusted models",
                    reason=(
                        "The collective model wording has not been accepted "
                        "as an application-owned record set."
                    ),
                ),
            ),
        )

        self.assertEqual(
            trace.candidate_quantity_labels,
            ("DIC", "pD", "Residual Deviance"),
        )
        self.assertEqual(
            trace.referent_bindings[0].origin,
            ReferentBindingOrigin.LITERAL,
        )
        self.assertEqual(
            trace.unresolved_dependencies[0].expression,
            "adjusted models",
        )

    def test_trace_without_bindings_is_valid(self):
        trace = AtomicQuestionEvidenceTrace(
            proposed_question=self.question,
            permitted_record_ids=("record-01", "record-02"),
            candidate_quantity_labels=("DIC",),
            permitted_evidence_ids=(
                self.left.evidence_id,
                self.right.evidence_id,
            ),
        )

        self.assertEqual(trace.referent_bindings, ())
        self.assertEqual(trace.unresolved_dependencies, ())

    def test_trace_rejects_out_of_scope_referent_id(self):
        with self.assertRaisesRegex(
            ValueError,
            "Referent binding contains an ID outside permitted scope",
        ):
            AtomicQuestionEvidenceTrace(
                proposed_question=self.question,
                permitted_record_ids=("record-01",),
                candidate_quantity_labels=("DIC",),
                permitted_evidence_ids=(self.left.evidence_id,),
                referent_bindings=(
                    ProposedReferentBinding(
                        expression="DIC",
                        referenced_ids=("evidence-not-permitted",),
                        origin=ReferentBindingOrigin.MODEL_PROPOSED,
                    ),
                ),
            )

    def test_candidate_quantity_label_is_not_a_referent_id(self):
        with self.assertRaisesRegex(
            ValueError,
            "Referent binding contains an ID outside permitted scope",
        ):
            AtomicQuestionEvidenceTrace(
                proposed_question=self.question,
                permitted_record_ids=("record-01",),
                candidate_quantity_labels=("DIC",),
                permitted_evidence_ids=(self.left.evidence_id,),
                referent_bindings=(
                    ProposedReferentBinding(
                        expression="DIC",
                        referenced_ids=("DIC",),
                        origin=ReferentBindingOrigin.LITERAL,
                    ),
                ),
            )

    def test_trace_rejects_duplicate_referent_expression(self):
        with self.assertRaisesRegex(
            ValueError,
            "Duplicate referent binding expression",
        ):
            AtomicQuestionEvidenceTrace(
                proposed_question=self.question,
                permitted_record_ids=("record-01",),
                candidate_quantity_labels=("DIC",),
                permitted_evidence_ids=(
                    self.left.evidence_id,
                    self.right.evidence_id,
                ),
                referent_bindings=(
                    ProposedReferentBinding(
                        expression="DIC",
                        referenced_ids=(self.left.evidence_id,),
                        origin=ReferentBindingOrigin.LITERAL,
                    ),
                    ProposedReferentBinding(
                        expression=" dic ",
                        referenced_ids=(self.right.evidence_id,),
                        origin=ReferentBindingOrigin.MODEL_PROPOSED,
                    ),
                ),
            )

    def test_trace_rejects_duplicate_scope_ids(self):
        with self.assertRaisesRegex(
            ValueError,
            "permitted_record_ids must not contain duplicates",
        ):
            AtomicQuestionEvidenceTrace(
                proposed_question=self.question,
                permitted_record_ids=("record-01", "record-01"),
                candidate_quantity_labels=("DIC",),
                permitted_evidence_ids=(self.left.evidence_id,),
            )

    def test_all_referent_decision_states_are_representable(self):
        proposal = ProposedReferentBinding(
            expression="DIC",
            referenced_ids=(self.left.evidence_id,),
            origin=ReferentBindingOrigin.LITERAL,
        )

        for state in ReferentAcceptanceState:
            decision = ReferentBindingDecision(
                proposed_binding=proposal,
                state=state,
                reason="Synthetic application decision.",
            )
            self.assertIs(decision.proposed_binding, proposal)
            self.assertIs(decision.state, state)

    def test_referent_decision_preserves_exact_proposal(self):
        proposal = ProposedReferentBinding(
            expression="RD",
            referenced_ids=(self.right.evidence_id,),
            origin=ReferentBindingOrigin.MODEL_PROPOSED,
        )
        decision = ReferentBindingDecision(
            proposed_binding=proposal,
            state=ReferentAcceptanceState.UNRESOLVED,
            reason="Semantic correspondence has not been accepted.",
        )

        self.assertIs(decision.proposed_binding, proposal)
        self.assertEqual(decision.proposed_binding.expression, "RD")
        self.assertEqual(
            decision.proposed_binding.referenced_ids,
            (self.right.evidence_id,),
        )

    def test_referent_decision_rejects_non_binding_object(self):
        with self.assertRaisesRegex(
            TypeError,
            "proposed_binding must be a ProposedReferentBinding",
        ):
            ReferentBindingDecision(
                proposed_binding="DIC",
                state=ReferentAcceptanceState.ACCEPTED,
                reason="Invalid synthetic decision.",
            )

    def test_referent_decision_requires_reason(self):
        proposal = ProposedReferentBinding(
            expression="DIC",
            referenced_ids=(self.left.evidence_id,),
            origin=ReferentBindingOrigin.LITERAL,
        )

        with self.assertRaisesRegex(
            ValueError,
            "reason must be non-empty text",
        ):
            ReferentBindingDecision(
                proposed_binding=proposal,
                state=ReferentAcceptanceState.ACCEPTED,
                reason=" ",
            )

    def promotion_trace(self, *, unresolved=False):
        binding = ProposedReferentBinding(
            expression="adjusted models",
            referenced_ids=("record-02",),
            origin=ReferentBindingOrigin.MANUAL,
        )
        dependencies = ()
        if unresolved:
            dependencies = (
                UnresolvedQuestionDependency(
                    expression="original omitted clause",
                    reason="Not required by the explicitly reformulated target.",
                ),
            )
        trace = AtomicQuestionEvidenceTrace(
            proposed_question=self.question,
            permitted_record_ids=("record-01", "record-02"),
            candidate_quantity_labels=("DIC",),
            permitted_evidence_ids=(
                self.left.evidence_id,
                self.right.evidence_id,
            ),
            referent_bindings=(binding,),
            unresolved_dependencies=dependencies,
        )
        return trace, binding

    def construction(self, trace, binding, **changes):
        decision = ReferentBindingDecision(
            proposed_binding=binding,
            state=ReferentAcceptanceState.ACCEPTED,
            reason="Accepted local interpretation for this target only.",
        )
        values = {
            "trace": trace,
            "relied_on_binding_decisions": (decision,),
            "proposition": (
                "For record-01 and record-02, the reported DIC difference "
                "establishes model fit improvement."
            ),
            "selected_record_ids": ("record-01", "record-02"),
            "selected_evidence_ids": (
                self.left.evidence_id,
                self.right.evidence_id,
            ),
            "evidence_package_id": "package-s9",
            "package_snapshot_id": "sha256:s9",
            "scope_reason": (
                "Explicitly reformulated to the two named records."
            ),
            "decision": PromotionDecision.PROMOTED,
            "decision_maker": "human:test",
            "decision_reason": (
                "The local referent and subject scope were explicitly accepted."
            ),
        }
        values.update(changes)
        return AppraisalTargetConstruction(**values)

    def test_promoted_construction_accepts_exact_accepted_binding(self):
        trace, binding = self.promotion_trace()
        construction = self.construction(trace, binding)

        self.assertIs(construction.trace, trace)
        self.assertEqual(
            construction.decision,
            PromotionDecision.PROMOTED,
        )
        self.assertIs(
            construction.relied_on_binding_decisions[0].proposed_binding,
            binding,
        )

    def test_promoted_construction_rejects_nonaccepted_relied_binding(self):
        trace, binding = self.promotion_trace()

        for state in (
            ReferentAcceptanceState.REJECTED,
            ReferentAcceptanceState.UNRESOLVED,
        ):
            decision = ReferentBindingDecision(
                proposed_binding=binding,
                state=state,
                reason="Synthetic non-accepted decision.",
            )
            with self.assertRaisesRegex(
                ValueError,
                "PROMOTED construction cannot rely",
            ):
                self.construction(
                    trace,
                    binding,
                    relied_on_binding_decisions=(decision,),
                )

    def test_construction_rejects_binding_from_another_trace(self):
        trace, binding = self.promotion_trace()
        other_binding = ProposedReferentBinding(
            expression="DIC",
            referenced_ids=(self.left.evidence_id,),
            origin=ReferentBindingOrigin.LITERAL,
        )
        borrowed = ReferentBindingDecision(
            proposed_binding=other_binding,
            state=ReferentAcceptanceState.ACCEPTED,
            reason="Valid elsewhere, not in this trace.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "proposal absent from the trace",
        ):
            self.construction(
                trace,
                binding,
                relied_on_binding_decisions=(borrowed,),
            )

    def test_construction_rejects_scope_outside_trace(self):
        trace, binding = self.promotion_trace()

        with self.assertRaisesRegex(
            ValueError,
            "selected_record_ids contains an ID outside trace scope",
        ):
            self.construction(
                trace,
                binding,
                selected_record_ids=("record-elsewhere",),
            )

        with self.assertRaisesRegex(
            ValueError,
            "selected_evidence_ids contains an ID outside trace scope",
        ):
            self.construction(
                trace,
                binding,
                selected_evidence_ids=("evidence-valid-elsewhere",),
            )

    def test_construction_rejects_duplicate_relied_binding_decision(self):
        trace, binding = self.promotion_trace()
        decision = ReferentBindingDecision(
            proposed_binding=binding,
            state=ReferentAcceptanceState.ACCEPTED,
            reason="Accepted local interpretation.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate decision for one relied-on referent binding",
        ):
            self.construction(
                trace,
                binding,
                relied_on_binding_decisions=(decision, decision),
            )

    def test_withheld_construction_preserves_unresolved_binding(self):
        trace, binding = self.promotion_trace()
        unresolved = ReferentBindingDecision(
            proposed_binding=binding,
            state=ReferentAcceptanceState.UNRESOLVED,
            reason="The local denotation remains unresolved.",
        )

        construction = self.construction(
            trace,
            binding,
            relied_on_binding_decisions=(unresolved,),
            decision=PromotionDecision.WITHHELD,
            decision_reason="Target formulation remains unresolved.",
        )

        self.assertEqual(
            construction.decision,
            PromotionDecision.WITHHELD,
        )
        self.assertEqual(
            construction.relied_on_binding_decisions[0].state,
            ReferentAcceptanceState.UNRESOLVED,
        )

    def test_promoted_reformulation_may_preserve_trace_dependency(self):
        trace, binding = self.promotion_trace(unresolved=True)
        construction = self.construction(trace, binding)

        self.assertEqual(
            construction.decision,
            PromotionDecision.PROMOTED,
        )
        self.assertEqual(len(construction.trace.unresolved_dependencies), 1)


    def test_target_factory_copies_promoted_construction_exactly(self):
        trace, binding = self.promotion_trace()
        construction = self.construction(trace, binding)

        target = model_appraisal_target_from_construction(
            "target-s9-q2",
            construction,
        )

        self.assertEqual(target.target_id, "target-s9-q2")
        self.assertEqual(target.proposition, construction.proposition)
        self.assertEqual(
            target.evidence_package_id,
            construction.evidence_package_id,
        )
        self.assertEqual(
            target.package_snapshot_id,
            construction.package_snapshot_id,
        )
        self.assertEqual(
            target.permitted_evidence_ids,
            construction.selected_evidence_ids,
        )

    def test_target_factory_rejects_withheld_construction(self):
        trace, binding = self.promotion_trace()
        construction = self.construction(
            trace,
            binding,
            decision=PromotionDecision.WITHHELD,
            decision_reason="Target remains withheld.",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Only a PROMOTED construction",
        ):
            model_appraisal_target_from_construction(
                "target-withheld",
                construction,
            )

    def test_target_factory_delegates_target_validation(self):
        trace, binding = self.promotion_trace()
        construction = self.construction(trace, binding)

        with self.assertRaisesRegex(
            ValueError,
            "target_id",
        ):
            model_appraisal_target_from_construction(
                " ",
                construction,
            )

    def test_target_factory_rejects_nonconstruction_object(self):
        with self.assertRaisesRegex(
            TypeError,
            "construction must be an AppraisalTargetConstruction",
        ):
            model_appraisal_target_from_construction(
                "target-invalid",
                object(),
            )



if __name__ == "__main__":
    unittest.main()
