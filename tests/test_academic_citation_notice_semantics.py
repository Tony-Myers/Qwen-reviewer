"""Offline reader semantics; verification and presentation remain authoritative."""
import copy
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

import academic_check_further as cf
import academic_chat as chat
import academic_orchestrator as o
import academic_reconciliation_orchestrator as lifecycle
import academic_tools as t


def candidate():
    return t.ReferenceCandidate('Related title', ['Author'], 2006, 'Journal',
                                '10.1000/related', 'article', title_similarity=.2)


def reference(status='not_verified', *, retained=None, related=None, conflict=False,
              corroboration='complete', issues=None):
    return t.AcademicReferenceResult(
        t.VerificationResult(status, retained, [], related_candidate=related),
        None, None, conflict, [], corroboration_status=corroboration, issues=issues or [])


class CitationNoticeTests(unittest.TestCase):
    def assess(self, refs, linked=None):
        if linked is None:
            linked = range(len(refs))
        result = NS(
            release=o.AcademicReleaseAssessment('release_allowed', True, []),
            references=[o.VerifiedReferenceProposal(
                chat.AcademicReference(f'Proposal {i}', None, None, None, None), ref)
                for i, ref in enumerate(refs)],
            source_claims=[NS(claim=chat.SourceClaim('A claim', i)) for i in linked],
            local_guidance=o.LocalGuidanceResult([]), technical_claims=[],
            discovered_claim_assessments=[])
        before = copy.deepcopy(result)
        eligibility = [o.resolve_retrieval_identity(r) for r in refs]
        presentation = lifecycle.decide_presentation(result.release, revised=False)
        assessment = cf.assess_check_further(result, NS(references_for=lambda *a: []))
        self.assertEqual(result, before)
        self.assertEqual(eligibility, [o.resolve_retrieval_identity(r) for r in refs])
        self.assertEqual(presentation, lifecycle.decide_presentation(result.release, revised=False))
        # Citation identity categories do not change the independent evidence state.
        self.assertEqual(assessment.state,
                         'incomplete' if assessment.bibliographic_limitations else 'outside_guidance')
        return assessment

    def test_related_record_and_skipped_title_remain_separate(self):
        issue = t.BibliographicIssue('title_corroboration', 'openalex', 'skipped', 'unsafe_title_query')
        a = self.assess([reference(related=candidate(), corroboration='unavailable', issues=[issue])])
        self.assertIn('Title corroboration not attempted', a.bibliographic_limitations[0]['message'])
        self.assertEqual(a.citation_notice['message'],
            'A related published record was found, but it did not establish the bibliographic identity '
            'of the citation as given. Check the citation before relying on it.')
        self.assertEqual(a.citation_notice['unmatched'], [])
        self.assertEqual(len(a.citation_notice['related_unverified']), 1)

    def test_probable_and_not_verified_retained_candidates(self):
        for status in ['probable', 'not_verified']:
            with self.subTest(status=status):
                a = self.assess([reference(status, retained=candidate())])
                self.assertIn('A related published record was found', a.citation_notice['message'])
                self.assertFalse(a.citation_notice['unmatched'])

    def test_completed_no_match_including_doi_recovery_and_rejected_candidates(self):
        for doi in [None, '10.1000/missing']:
            for candidates in [[], [candidate()]]:
                with self.subTest(doi=doi, candidates=candidates), patch.object(t, 'resolve_doi', return_value=None), patch.object(t, 'search_crossref', return_value=candidates):
                    verified = t.verify_reference(title='Proposed title', doi=doi)
                self.assertEqual(verified.status, 'not_verified')
                ref = reference()
                ref.crossref_verification = verified
                a = self.assess([ref])
                self.assertEqual(a.citation_notice['message'],
                    'A source given in support of this answer could not be matched to a published record. '
                    'Check the citation before relying on it.')
                self.assertFalse(a.citation_notice['related_unverified'])

    def test_conflicts_override_retained_records(self):
        for ref in [reference('metadata_conflict', retained=candidate()),
                    reference(related=candidate(), conflict=True),
                    reference('verified', retained=candidate(), conflict=True)]:
            a = self.assess([ref])
            self.assertIn('conflict with the published record', a.citation_notice['message'])
            self.assertFalse(a.citation_notice['related_unverified'])
            self.assertFalse(a.citation_notice['unmatched'])

    def test_unavailable_and_verified_incomplete_corroboration(self):
        for status, outcome, code in [('unavailable', 'unavailable', 'http_error'),
                                      ('verified', 'skipped', 'unsafe_title_query'),
                                      ('verified', 'unavailable', 'http_error')]:
            issue = t.BibliographicIssue('title_corroboration', 'openalex', outcome, code)
            a = self.assess([reference(status, retained=candidate(),
                corroboration='unavailable', issues=[issue])])
            self.assertIsNone(a.citation_notice)
            self.assertTrue(a.bibliographic_limitations)
        self.assertIsNone(self.assess([reference('verified', retained=candidate())]).citation_notice)

    def test_mixed_plural_and_unlinked(self):
        refs = [reference(), reference(), reference('metadata_conflict'),
                reference(conflict=True), reference(related=candidate()),
                reference('probable', retained=candidate()), reference('future'), reference('future')]
        a = self.assess(refs)
        for category in ['unmatched', 'conflicting', 'related_unverified', 'identity_unestablished']:
            self.assertEqual(len(a.citation_notice[category]), 2)
        for text in ['Some sources', 'details of some sources', 'Related published records',
                     'bibliographic identities of some citations', 'Check the citations before relying on them.']:
            self.assertIn(text, a.citation_notice['message'])
        self.assertIsNone(self.assess(refs, linked=[]).citation_notice)
        a = self.assess(refs, linked=[0, 2, 4])
        self.assertIn('A related published record', a.citation_notice['message'])
        self.assertIn('A source given', a.citation_notice['message'])
        self.assertIn('details of a source', a.citation_notice['message'])

    def test_unknown_status_is_neutral_even_with_candidate(self):
        for retained in [None, candidate()]:
            a = self.assess([reference('future_status', retained=retained)])
            self.assertTrue(a.citation_notice['identity_unestablished'])
            self.assertIn('available verification result does not establish', a.citation_notice['message'])
            self.assertNotIn('matched to a published record', a.citation_notice['message'])
            self.assertFalse(a.citation_notice['related_unverified'])


if __name__ == '__main__':
    unittest.main()
