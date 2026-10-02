#!/usr/bin/env python3
"""Partial global discovery retains evidence without claiming completion."""
import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import academic_chat as chat
import academic_claim_coverage as coverage
import academic_orchestrator as orchestrator
import academic_reconciliation_orchestrator as reconciliation
import academic_check_further as further
import academic_methodology as methodology
import llm_backend
import reviewer_notes
import server


ANSWER = 'Measure A increases precision. Measure B reduces bias. Measure C improves power.'


def item(letter):
    statement = dict(A='Measure A increases precision.', B='Measure B reduces bias.',
                     C='Measure C improves power.')[letter]
    return dict(type='methodological', concept=letter, statement=statement,
                parameterisation=None, source_anchor=statement)


class PartialCoverageTests(unittest.TestCase):
    def pipeline(self, proposals, *, recover=False, answer=ANSWER):
        audit_prompts = []
        stages = []
        def assessor(*, prompt, schema):
            if schema == coverage.claim_discovery_output_schema():
                if 'ANSWER DRAFT' in prompt:
                    stages.append('global')
                    return {'discovered_claims': proposals}
                stages.append('audit')
                audit_prompts.append(prompt)
                if recover and 'SOURCE SENTENCE\nMeasure B reduces bias.' in prompt:
                    self.assertIn('ALREADY EXTRACTED FROM THIS SENTENCE\n(none)', prompt)
                    return {'discovered_claims': [item('B')]}
                return {'discovered_claims': []}
            if schema == coverage.claim_decomposition_output_schema():
                stages.append('decomposition')
                return {'requires_decomposition': False, 'atomic_claims': []}
            if schema == coverage.claim_representation_output_schema():
                stages.append('representation')
                return {'represented': False, 'represented_by': None}
            raise AssertionError(schema)
        result = coverage.assess_claim_coverage_two_stage(
            answer_draft=answer, existing_claims=[], assessor=assessor)
        return result, stages

    def test_valid_invalid_valid_and_original_indices(self):
        bad = dict(item('B'), source_anchor='invented ... anchor')
        result, stages = self.pipeline([item('A'), bad, item('C')])
        self.assertEqual([x.claim.statement for x in result.discovered_claims],
                         [item('A')['statement'], item('C')['statement']])
        self.assertEqual([r.index for r in result.rejected_global_items], [1])
        self.assertIn('verbatim contiguous span', result.rejected_global_items[0].reason)
        self.assertEqual(stages.count('audit'), 3)
        self.assertEqual(stages.count('decomposition'), 2)
        self.assertEqual(stages.count('representation'), 2)
        self.assertEqual(coverage.ClaimCoverageAssessment.from_result(result).status,
                         coverage.COVERAGE_STATUS_UNAVAILABLE)

    def test_multiple_and_all_rejected(self):
        for proposals, indices, retained in [
            ([None, item('B'), dict(item('C'), parameterisation='')], [0, 2], 1),
            ([None, dict(item('B'), source_anchor='not in answer')], [0, 1], 0),
        ]:
            with self.subTest(indices=indices):
                result, stages = self.pipeline(proposals)
                self.assertEqual([r.index for r in result.rejected_global_items], indices)
                self.assertTrue(all(r.reason for r in result.rejected_global_items))
                self.assertEqual(len(result.discovered_claims), retained)
                self.assertEqual(stages.count('audit'), 3)
                assessment = coverage.ClaimCoverageAssessment.from_result(result)
                self.assertIs(assessment.result, result)
                self.assertEqual(assessment.status, coverage.COVERAGE_STATUS_UNAVAILABLE)

    def test_audit_recovery_does_not_clear_incompleteness(self):
        result, _ = self.pipeline([item('A'), dict(item('B'), source_anchor='bad'),
                                   item('C')], recover=True)
        self.assertEqual({x.claim.statement for x in result.discovered_claims},
                         {item(x)['statement'] for x in 'ABC'})
        self.assertEqual(len(result.rejected_global_items), 1)
        self.assertEqual(coverage.ClaimCoverageAssessment.from_result(result).status,
                         coverage.COVERAGE_STATUS_UNAVAILABLE)

    def test_decomposition_and_representation_cannot_clear_rejection(self):
        answer = 'Measure A increases precision and measure B reduces bias.'
        parent = dict(item('A'), statement=answer, source_anchor=answer)
        children = [dict(item('A'), source_anchor='Measure A increases precision'),
                    dict(item('B'), source_anchor='measure B reduces bias')]
        existing = [chat.TechnicalClaim('methodological', 'A',
                                       'Measure A improves precision.', None)]
        def assessor(*, prompt, schema):
            if schema == coverage.claim_discovery_output_schema():
                return {'discovered_claims': [parent, None] if 'ANSWER DRAFT' in prompt else []}
            if schema == coverage.claim_decomposition_output_schema():
                return {'requires_decomposition': True, 'atomic_claims': children}
            return {'represented': True, 'represented_by': 1}
        result = coverage.assess_claim_coverage_two_stage(
            answer_draft=answer, existing_claims=existing, assessor=assessor)
        self.assertEqual(len(result.discovered_claims), 2)
        self.assertEqual(result.missing_claims, [])
        self.assertEqual([r.index for r in result.rejected_global_items], [1])
        self.assertEqual(coverage.ClaimCoverageAssessment.from_result(result).status,
                         coverage.COVERAGE_STATUS_UNAVAILABLE)

    def test_placement_rejection_preserves_siblings(self):
        bad = dict(item('B'), source_anchor='precision. Measure B')
        result, _ = self.pipeline([item('A'), bad, item('C')])
        self.assertEqual(len(result.discovered_claims), 2)
        self.assertIn('ClaimSourcePlacementError', result.rejected_global_items[0].reason)
        self.assertEqual(result.rejected_global_items[0].index, 1)

    def test_placement_programming_error_is_not_quarantined(self):
        with patch.object(coverage, 'resolve_claim_source_context',
                          side_effect=ValueError('programming defect')):
            with self.assertRaisesRegex(ValueError, 'programming defect'):
                self.pipeline([item('A')])

    def test_success_contract_unchanged(self):
        result, _ = self.pipeline([item('A'), item('C')])
        self.assertEqual(result.rejected_global_items, [])
        assessment = coverage.ClaimCoverageAssessment.from_result(result)
        self.assertEqual(assessment.status, coverage.COVERAGE_STATUS_MISSING_FOUND)
        self.assertEqual(assessment.reasons, [])
        self.assertEqual(set(assessment.to_dict()), {'status', 'missing_claims', 'reasons'})

    def checked_draft(self, result, *, answer=ANSWER):
        calls = []
        passage = reviewer_notes.Passage('test', 'test', 'Synthetic guidance.', 1.0)
        def method(*, prompt, schema):
            calls.append('methodology')
            return {'status': methodology.METHODOLOGICAL_STATUS_CONSISTENT,
                    'reason': 'Synthetic compatible guidance.'}
        def restriction(*, prompt, schema):
            calls.append('restriction')
            return {'material_restriction_omitted': True}
        checked = orchestrator.assess_academic_draft(
            chat.AcademicDraft(answer, [], [], []),
            local_guidance=orchestrator.LocalGuidanceResult([]),
            coverage_assessor=lambda **kwargs: coverage.ClaimCoverageAssessment.from_result(result),
            methodological_assessor=method,
            claim_methodological_retriever=lambda query: orchestrator.LocalGuidanceResult([passage]),
            material_restriction_assessor=restriction)
        return checked, calls

    def test_downstream_checks_and_presentation(self):
        result, _ = self.pipeline([item('A'), None, item('C')])
        checked, calls = self.checked_draft(result)
        self.assertEqual(len(checked.technical_claims), 2)
        self.assertEqual(len(checked.discovered_claim_assessments), 2)
        self.assertEqual(calls.count('restriction'), 2)
        self.assertEqual(calls.count('methodology'), 4)  # Contextual and standalone.
        self.assertTrue(all(x.verification is not None for x in checked.technical_claims))
        self.assertEqual(checked.release.status, 'checking_incomplete')
        self.assertFalse(checked.release.safe_to_present)
        self.assertEqual(reconciliation.decide_presentation(checked.release, revised=False).mode,
                         'qualified')
        self.assertEqual(reconciliation.decide_presentation(checked.release, revised=True).mode,
                         'withheld')
        self.assertEqual(further.assess_check_further(checked, reviewer_notes.NotesIndex()).state,
                         further.STATE_INCOMPLETE)
        public = json.dumps(checked.to_dict())
        self.assertNotIn('rejected_global_items', public)
        self.assertNotIn('must be an object', public)

    def test_retained_real_deterministic_conflict_has_precedence(self):
        answer = 'The relative efficiency is RE = 1 + lambda/M.'
        proposal = dict(type='formula', concept='multiple imputation relative efficiency',
                        statement='RE = 1 + lambda/M',
                        parameterisation='lambda is the fraction of missing information; M is the number of imputations',
                        source_anchor='RE = 1 + lambda/M')
        result, _ = self.pipeline([None, proposal], answer=answer)
        checked, _ = self.checked_draft(result, answer=answer)
        self.assertEqual(checked.release.status, 'blocked_technical_conflict')
        self.assertFalse(checked.release.safe_to_present)
        self.assertEqual(checked.claim_coverage.status, coverage.COVERAGE_STATUS_UNAVAILABLE)
        self.assertEqual(reconciliation.decide_presentation(checked.release, revised=False).mode,
                         'withheld')

    def test_source_contradiction_has_precedence(self):
        result, _ = self.pipeline([None, item('A')])
        release = orchestrator.assess_academic_release(
            [], [SimpleNamespace(claim_assessment=SimpleNamespace(status='claim_contradicted'))],
            claim_coverage=coverage.ClaimCoverageAssessment.from_result(result))
        self.assertEqual(release.status, 'blocked_source_contradiction')
        self.assertFalse(release.safe_to_present)

    def test_server_diagnostics_and_public_payload(self):
        raw = json.dumps({'discovered_claims': [item('A'), dict(item('B'), source_anchor='PRIVATE BAD ANCHOR'), item('C')]})
        def generate(model, tokenizer, messages, **kwargs):
            prompt = messages[0]['content']
            if 'ANSWER DRAFT' in prompt:
                return raw
            if 'ALREADY EXTRACTED' in prompt:
                return '{"discovered_claims": []}'
            if 'EXTRACTED CLAIM' in prompt:
                return '{"requires_decomposition": false, "atomic_claims": []}'
            return '{"represented": false, "represented_by": null}'
        with patch.object(llm_backend, 'generate', side_effect=generate):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                assessment = server.assess_academic_claim_coverage(answer_draft=ANSWER, existing_claims=[])
        self.assertIn('global discovery item rejected index=1', stderr.getvalue())
        self.assertIn('verbatim contiguous span', stderr.getvalue())
        self.assertIn(repr(raw), stderr.getvalue())
        self.assertNotIn('global discovery failed', stderr.getvalue())
        self.assertEqual(len(assessment.result.discovered_claims), 2)
        self.assertEqual(assessment.reasons, ['Local claim-coverage output could not be validated.'])
        public = json.dumps(assessment.to_dict())
        for secret in ('PRIVATE BAD ANCHOR', 'verbatim contiguous span', 'rejected_items', 'raw assessor'):
            self.assertNotIn(secret, public)


if __name__ == '__main__':
    unittest.main()
