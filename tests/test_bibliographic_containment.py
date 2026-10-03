"""Offline Stage 3 evidence containment, disclosure and provenance contracts."""
import asyncio
import contextlib
import copy
import io
import json
import re
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import academic_tools as t
import academic_chat as chat
import academic_orchestrator as o
import academic_check_further as cf
import academic_reconciliation_orchestrator as lifecycle


def failure(service='crossref', code='http_error', status=400):
    return t.BibliographicLookupError('PRIVATE_EXCEPTION', service=service,
        operation='title_search', code=code, http_status=status)


def candidate(title='Safe Title', doi='10.1000/safe'):
    return t.ReferenceCandidate(title, ['Ada'], 2024, 'Journal', doi, 'article', title_similarity=1)


def checked(title='Safe Title', doi='10.1000/safe'):
    return t.VerificationResult('verified', candidate(title, doi), ['Completed'])


def unavailable():
    with patch.object(t, 'verify_reference', side_effect=failure()), contextlib.redirect_stderr(io.StringIO()):
        return t.verify_academic_reference(title='Failed Title', doi='10.1000/failed')


def evidence_result(reference, linked=True):
    return NS(release=o.AcademicReleaseAssessment('release_allowed', True, []),
        references=[o.VerifiedReferenceProposal(chat.AcademicReference('Failed Title', None, None, None, '10.1000/failed'), reference)],
        source_claims=[NS(claim=chat.SourceClaim('A claim', 0))] if linked else [],
        local_guidance=o.LocalGuidanceResult([]), technical_claims=[], discovered_claim_assessments=[])


class ContainmentTests(unittest.TestCase):
    def test_crossref_transport_failures_contained(self):
        for error, code in [(HTTPError('u', 400, 'Bad Request', {}, None), 'http_error'),
                            (URLError('offline'), 'network_error'), (TimeoutError('slow'), 'timeout')]:
            with patch.object(t, 'urlopen', side_effect=error), contextlib.redirect_stderr(io.StringIO()) as log:
                result = t.verify_academic_reference(title='Failed Title')
            self.assertEqual(result.crossref_verification.status, 'unavailable')
            self.assertEqual(result.issues[0].stage, 'reference_verification')
            self.assertEqual(result.issues[0].code, code)
            self.assertEqual(result.issues[0].outcome, 'unavailable')
            self.assertEqual(o.resolve_retrieval_identity(result).status, 'not_eligible')
            self.assertIn('Traceback', log.getvalue())
            self.assertNotIn('PRIVATE_EXCEPTION', json.dumps(result.to_dict()))

    def test_openalex_retry_exhaustion_and_bad_json(self):
        for status in [400, 429, 503]:
            with patch.object(t, 'verify_reference', return_value=checked()), patch.object(t, '_crossref_candidates', return_value=[candidate()]), patch.object(t, 'urlopen', side_effect=HTTPError('u', status, 'Rejected', {}, None)) as transport, patch.object(t.time, 'sleep'), contextlib.redirect_stderr(io.StringIO()):
                result = t.verify_academic_reference(title='Safe Title')
            self.assertEqual(transport.call_count, 3 if status in [429,503] else 1)
            self.assertEqual(result.crossref_verification.status, 'verified')
            self.assertEqual(result.issues[0].http_status, status)
            self.assertEqual(result.issues[0].service, 'openalex')
            self.assertEqual(result.issues[0].stage, 'title_corroboration')
            self.assertNotIn('outage', result.bibliographic_notice())
            self.assertEqual(o.resolve_retrieval_identity(result).status, 'not_eligible')
        for raw in [b'invalid', b'{"message": []}']:
            with patch.object(t, 'urlopen', return_value=io.BytesIO(raw)), contextlib.redirect_stderr(io.StringIO()):
                result = t.verify_academic_reference(title='Safe Title')
            self.assertEqual(result.issues[0].code, 'malformed_response')

    def test_later_failures_retain_evidence_and_conflict(self):
        for service in ['crossref', 'openalex']:
            verification = checked()
            verification.status = 'metadata_conflict'
            with patch.object(t, 'verify_reference', return_value=verification), patch.object(t, 'resolve_doi', return_value=candidate()), patch.object(t, 'resolve_openalex_doi', return_value=candidate()), patch.object(t, '_crossref_candidates', side_effect=failure(service)) if service == 'crossref' else patch.object(t, '_crossref_candidates', return_value=[candidate()]), patch.object(t, 'search_openalex', side_effect=failure('openalex')), contextlib.redirect_stderr(io.StringIO()):
                result = t.verify_academic_reference(title='Safe Title', doi='10.1000/safe')
            self.assertIs(result.crossref_verification, verification)
            self.assertEqual(result.crossref_verification.status, 'metadata_conflict')
            self.assertEqual(result.doi_corroboration.status, 'corroborated')
            self.assertEqual(result.issues[0].service, service)

    def test_programming_errors_propagate_and_logging_cannot_break_containment(self):
        for error in [RuntimeError('bug'), TypeError('bug'), AttributeError('bug'), AssertionError('bug')]:
            for stage in ['verify_reference', '_crossref_candidates', 'search_openalex']:
                with patch.object(t, 'verify_reference', return_value=checked()), patch.object(t, '_crossref_candidates', return_value=[]), patch.object(t, stage, side_effect=error):
                    with self.assertRaises(type(error)) as caught:
                        t.verify_academic_reference(title='Safe Title')
                self.assertIs(caught.exception, error)
        with patch.object(t, 'verify_reference', side_effect=failure()), patch.object(t.traceback, 'print_exc', side_effect=OSError('stderr')):
            self.assertEqual(t.verify_academic_reference(title='Safe Title').crossref_verification.status, 'unavailable')

    def test_mixed_references_continue_with_source_gates(self):
        refs=[chat.AcademicReference('Failed Title',None,None,None,'10.1000/failed'), chat.AcademicReference('Safe Title',None,None,None,'10.1000/safe')]
        draft=chat.AcademicDraft('Locally generated answer',refs,[chat.SourceClaim('First',0),chat.SourceClaim('Second',1)],[])
        good=t.AcademicReferenceResult(checked(),t.corroborate_candidates(candidate(),candidate()),None,False,[])
        bad=unavailable()
        discover=Mock(return_value=NS(status='location_found',doi='10.1000/safe'))
        retrieve=Mock(return_value=NS(status='retrieved'))
        locate=Mock(return_value=NS(status='claim_located',evidence=[]))
        assess=Mock(return_value=NS(status='claim_supported'))
        result=o.assess_academic_draft(draft,local_guidance=o.LocalGuidanceResult([]),
            reference_verifier=lambda **kw: bad if kw['title']=='Failed Title' else good,
            source_discoverer=discover,source_retriever=retrieve,claim_locator=locate,claim_assessor=assess)
        discover.assert_called_once_with('10.1000/safe')
        retrieve.assert_called_once();locate.assert_called_once();assess.assert_called_once()
        blocked=result.source_claims[0]
        self.assertEqual(blocked.retrieval_identity.status,'not_eligible')
        self.assertIsNone(blocked.source_retrieval);self.assertIsNone(blocked.claim_location);self.assertIsNone(blocked.claim_assessment)
        self.assertEqual(result.source_claims[1].claim_assessment.status,'claim_supported')
        self.assertTrue(result.release.safe_to_present)
        self.assertNotEqual(result.release.status,'checking_incomplete')
        self.assertEqual(lifecycle.decide_presentation(result.release,revised=False).mode,'release')
        self.assertEqual(result.references[0].proposed_reference.title,'Failed Title')

    def test_linked_disclosure_precedence_and_unlinked_isolation(self):
        index=NS(references_for=lambda *args: [])
        result=evidence_result(unavailable())
        assessment=cf.assess_check_further(result,index)
        self.assertEqual(assessment.state,'incomplete')
        self.assertIsNone(assessment.citation_notice)
        self.assertEqual(assessment.bibliographic_limitations[0]['reference_index'],0)
        self.assertIn('required bibliographic identity',assessment.bibliographic_limitations[0]['source_checking'])
        result.release=o.AcademicReleaseAssessment('blocked_source_contradiction',False,[])
        self.assertEqual(cf.assess_check_further(result,index).state,'worth_checking')
        self.assertTrue(cf.assess_check_further(result,index).bibliographic_limitations)
        result=evidence_result(unavailable(),linked=False)
        actual=cf.assess_check_further(result,index)
        baseline=copy.copy(result);baseline.references=[]
        self.assertEqual(actual.state,cf.assess_check_further(baseline,index).state)
        self.assertFalse(actual.bibliographic_limitations)
        self.assertNotIn('bibliographic_limitations',actual.to_dict())

    def test_failed_revision_cannot_clear_contradiction(self):
        revised=evidence_result(unavailable())
        revised.source_claims[0].reference=revised.references[0]
        revised.source_claims[0].claim_assessment=None
        initial=copy.deepcopy(revised)
        initial.release=o.AcademicReleaseAssessment('blocked_source_contradiction',False,[])
        initial.source_claims[0].claim_assessment=NS(status='claim_contradicted',evidence=[])
        resolution=lifecycle.assess_source_contradiction_resolution(initial,revised)
        self.assertNotEqual(resolution.status,'resolved')
        self.assertEqual(resolution.sources[0].outcome,'resolution_not_established')

    def test_methodological_concern_and_further_reading_precedence(self):
        result=evidence_result(unavailable())
        passage=NS(note='Note',heading='Topic',score=1)
        result.local_guidance=o.LocalGuidanceResult([passage])
        method=NS(status='methodological_consistency_not_established',passages=[passage],reasons=[])
        result.technical_claims=[NS(claim=chat.TechnicalClaim('interpretation','Topic','A point',None),methodological_consistency=method)]
        index=NS(references_for=lambda *args: [NS(doi='10.1000/reading')])
        assessment=cf.assess_check_further(result,index)
        self.assertTrue(assessment.groups)
        self.assertEqual(assessment.state,'incomplete')
        self.assertTrue(assessment.bibliographic_limitations)
        method.status='methodological_conflict'
        assessment=cf.assess_check_further(result,index)
        self.assertEqual(assessment.state,'worth_checking')
        self.assertTrue(assessment.worth_checking)
        self.assertTrue(assessment.bibliographic_limitations)

    def test_endpoint_returns_answer_with_unchanged_presentation_policy(self):
        import server
        draft=chat.AcademicDraft('ANSWER_SENTINEL',
            [chat.AcademicReference('Failed Title',None,None,None,None)],
            [chat.SourceClaim('A claim',0)],[])
        def first_stage(*args,**kwargs):
            return o.assess_academic_draft(draft,local_guidance=o.LocalGuidanceResult([]))
        with patch.object(server,'ensure_model',return_value=None), patch.object(server.academic_orchestrator,'run_academic_first_stage',side_effect=first_stage), patch.object(t,'verify_reference',side_effect=failure()), patch.object(o,'methodological_notes_index',return_value=NS(references_for=lambda *args: [])), contextlib.redirect_stderr(io.StringIO()):
            payload=asyncio.run(server.academic_chat_first_stage({'question':'Test'}))
        self.assertIsInstance(payload,dict)
        self.assertEqual(payload['answer_draft'],'ANSWER_SENTINEL')
        self.assertEqual(payload['presentation']['mode'],'release')
        self.assertTrue(payload['release']['safe_to_present'])
        self.assertNotEqual(payload['release']['status'],'checking_incomplete')
        self.assertEqual(payload['check_further']['state'],'incomplete')
        self.assertIn('bibliographic_limitations',payload['check_further'])

    def test_real_frontend_disclosure_has_no_exception_details(self):
        result=evidence_result(unavailable())
        cf_payload=cf.assess_check_further(result,NS(references_for=lambda *args: [])).to_dict()
        functions='\n'.join(re.findall(r'^function \w+\(.*?\n}\n',Path('app/chat.html').read_text(),re.S|re.M))
        script=functions+'\nprocess.stdout.write(renderAcademicReference('+json.dumps(result.references[0].to_dict())+',0)+renderAcademicCheckFurther('+json.dumps(cf_payload)+',"",""));'
        rendered=subprocess.run(['node','-e',script],capture_output=True,text=True,check=True).stdout
        self.assertIn('Bibliographic verification could not be completed',rendered)
        self.assertIn('source could not be checked against the claim',rendered)
        for forbidden in ['PRIVATE_EXCEPTION','OpenAlex was unavailable','matched to a published record']:
            self.assertNotIn(forbidden,rendered)

if __name__=='__main__':
    unittest.main()
