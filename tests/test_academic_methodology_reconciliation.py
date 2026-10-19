#!/usr/bin/env python3
"""Asymmetric reconciliation shared by release, evidence and diagnostics."""
import json
import unittest
from types import SimpleNamespace as NS

import academic_chat as chat
import academic_claim_coverage as coverage
import academic_methodology as methodology
import academic_orchestrator as orchestrator
import academic_check_further as further
import academic_reconciliation_orchestrator as presentation
import academic_technical as technical
import reviewer_notes

CONSISTENT = methodology.METHODOLOGICAL_STATUS_CONSISTENT
CONFLICT = methodology.METHODOLOGICAL_STATUS_CONFLICT
UNKNOWN = methodology.METHODOLOGICAL_STATUS_NOT_ESTABLISHED
STATEMENT = ('Statistical significance indicates that the observed effect is unlikely '
             'to have occurred by chance under the null hypothesis.')
SENTENCE = (STATEMENT[:-1] + ', but it does not measure the magnitude or practical '
            'relevance of that effect.')


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = reviewer_notes.NotesIndex()
        cls.passages = [next(p for p in cls.index.passages
                            if p.heading == 'What does a *p*-value measure?')]

    def scenario(self, standalone_status, context_statuses, *, failed=(), restricted=True):
        claim = chat.TechnicalClaim('interpretation', 'significance', STATEMENT, None)
        standalone = methodology.MethodologicalConsistencyResult(
            standalone_status, claim, self.passages, ['Original standalone reason.'])
        item = orchestrator.TechnicalClaimResult(
            claim, technical.TechnicalVerification(
                technical.TECHNICAL_STATUS_NOT_VERIFIED, 'test', '', []), standalone)
        contexts = []
        for i, status in enumerate(context_statuses):
            source = coverage.ClaimSourceContext(SENTENCE, 0, len(SENTENCE),
                                                SENTENCE, 0, len(SENTENCE))
            contextual = (None if status is None else
                methodology.ContextualMethodologicalConsistencyResult(
                    status, claim, source, self.passages, ['Original contextual reason.'],
                    'Synthetic failure' if i in failed else ''))
            contexts.append(orchestrator.DiscoveredClaimAssessment(
                coverage.DiscoveredClaim(claim, STATEMENT[:-1], 0, len(STATEMENT)-1),
                source, coverage.MaterialRestrictionAssessment(restricted), contextual))
        decision = orchestrator.reconcile_methodological_assessments(claim, standalone, contexts)
        release = orchestrator.assess_academic_release([item], [], contexts)
        result = NS(technical_claims=[item], discovered_claim_assessments=contexts,
                    local_guidance=orchestrator.LocalGuidanceResult(self.passages),
                    release=release, references=[], source_claims=[])
        evidence = further.assess_check_further(result, self.index).to_dict()
        row = evidence['diagnostics']['methodology_reconciliation'][0]
        self.assertEqual(row, {'statement': STATEMENT, **decision.to_dict()})
        self.assertEqual(standalone.status, standalone_status)
        self.assertEqual([None if c.contextual_methodological_consistency is None else
                          c.contextual_methodological_consistency.status for c in contexts],
                         context_statuses)
        self.assertTrue(release.safe_to_present)
        self.assertEqual(presentation.decide_presentation(release, revised=False).mode, 'release')
        ordinary = json.dumps({k:v for k,v in evidence.items() if k != 'diagnostics'})
        self.assertNotIn('retain_standalone', ordinary)
        self.assertNotIn('conflict_unresolved', ordinary)
        return decision, release, evidence

    def assert_concern(self, release, evidence):
        self.assertEqual(release.status, orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT)
        self.assertEqual(evidence['state'], further.STATE_WORTH_CHECKING)
        self.assertTrue(evidence['worth_checking'])
        self.assertGreater(evidence['diagnostics']['counts']['conflict'], 0)

    def test_conflict_unknown_live_p_value_shape(self):
        decision, release, evidence = self.scenario(CONFLICT, [UNKNOWN])
        self.assertEqual(decision.outcome, 'conflict_unresolved')
        self.assertTrue(decision.retain_standalone)
        self.assert_concern(release, evidence)
        self.assertEqual(evidence['worth_checking'][0]['text'], SENTENCE)
        self.assertEqual(evidence['further_reading'], [])

    def test_conflict_consistent_positive_clearance(self):
        decision, release, evidence = self.scenario(CONFLICT, [CONSISTENT])
        self.assertEqual(decision.outcome, 'conflict_positively_cleared')
        self.assertFalse(decision.retain_standalone)
        self.assertEqual(release.status, 'release_allowed_with_unverified_claims')
        self.assertEqual(evidence['diagnostics']['counts']['conflict'], 0)
        self.assertEqual(evidence['worth_checking'], [])

    def test_conflict_confirmed_in_context(self):
        decision, release, evidence = self.scenario(CONFLICT, [CONFLICT])
        self.assertEqual(decision.outcome, 'conflict_confirmed_in_context')
        self.assertFalse(decision.retain_standalone)
        self.assert_concern(release, evidence)
        self.assertEqual(evidence['diagnostics']['counts']['conflict'], 1)
        self.assertEqual(evidence['diagnostics']['conflicts'][0]['reasons'],
                         ['Original contextual reason.'])

    def test_unknown_consistent(self):
        decision, release, evidence = self.scenario(UNKNOWN, [CONSISTENT])
        self.assertFalse(decision.retain_standalone)
        self.assertEqual(evidence['diagnostics']['counts']['consistent'], 1)
        self.assertEqual(evidence['diagnostics']['counts']['not_established'], 0)

    def test_consistent_conflict(self):
        decision, release, evidence = self.scenario(CONSISTENT, [CONFLICT])
        self.assertFalse(decision.retain_standalone)
        self.assert_concern(release, evidence)

    def test_multiple_consistent_unknown(self):
        decision, release, evidence = self.scenario(CONFLICT, [CONSISTENT, UNKNOWN])
        self.assertEqual(decision.outcome, 'conflict_unresolved')
        self.assertTrue(decision.retain_standalone)
        self.assert_concern(release, evidence)

    def test_multiple_all_consistent(self):
        decision, release, evidence = self.scenario(CONFLICT, [CONSISTENT, CONSISTENT])
        self.assertEqual(decision.outcome, 'conflict_positively_cleared')
        self.assertFalse(decision.retain_standalone)
        self.assertEqual(evidence['worth_checking'], [])

    def test_missing_and_failed_context(self):
        for statuses, failed in [([None], ()), ([CONSISTENT], (0,)),
                                 ([CONSISTENT, None], ()),
                                 ([CONSISTENT, CONSISTENT], (1,))]:
            with self.subTest(statuses=statuses, failed=failed):
                decision, release, evidence = self.scenario(CONFLICT, statuses, failed=failed)
                self.assertTrue(decision.retain_standalone)
                self.assertEqual(decision.outcome, 'conflict_unresolved')
                self.assert_concern(release, evidence)

    def test_confirmed_conflict_does_not_clear_other_unknown_occurrence(self):
        decision, release, evidence = self.scenario(CONFLICT, [CONFLICT, UNKNOWN])
        self.assertTrue(decision.retain_standalone)
        self.assertEqual(decision.outcome, 'conflict_confirmed_in_context')
        self.assert_concern(release, evidence)

    def test_no_restriction_or_occurrence_cannot_clear(self):
        for contexts in ([], [CONSISTENT]):
            decision, release, evidence = self.scenario(CONFLICT, contexts, restricted=False)
            self.assertTrue(decision.retain_standalone)
            self.assert_concern(release, evidence)


if __name__ == '__main__':
    unittest.main()
