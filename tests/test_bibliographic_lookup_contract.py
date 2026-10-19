"""Offline contracts for bibliographic transport failures and public issues."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import academic_chat
import academic_tools as at
import academic_orchestrator as orchestrator


class BibliographicContractTests(unittest.TestCase):
    def test_http_metadata_and_cause(self):
        for service, call in [('openalex', lambda: at.search_openalex('Title')),
                              ('crossref', lambda: at.search_crossref('Title'))]:
            with self.subTest(service=service):
                error = HTTPError('https://example.test', 400, 'Bad Request', {}, None)
                with patch.object(at, 'urlopen', side_effect=error) as transport:
                    with self.assertRaises(at.BibliographicLookupError) as caught:
                        call()
                exc = caught.exception
                self.assertEqual((exc.service, exc.operation, exc.code, exc.http_status),
                                 (service, 'title_search', 'http_error', 400))
                self.assertIs(exc.__cause__, error)
                self.assertIsInstance(exc, RuntimeError)
                self.assertNotIsInstance(exc, at.OpenAlexUnavailableError)
                transport.assert_called_once()

    def test_network_timeout_and_decode(self):
        for getter, service in [(at._get_json, 'crossref'),
                                (at._get_openalex_json, 'openalex')]:
            for error, code in [(URLError('offline'), 'network_error'),
                                (TimeoutError('slow'), 'timeout'),
                                (URLError(TimeoutError('slow')), 'timeout')]:
                with self.subTest(service=service, code=code):
                    with patch.object(at, 'urlopen', side_effect=error):
                        with self.assertRaises(at.BibliographicLookupError) as caught:
                            getter('https://example.test/works')
                    self.assertEqual(caught.exception.code, code)
                    self.assertIs(caught.exception.__cause__, error)
            for raw in [b'{broken', b'\xff']:
                with patch.object(at, 'urlopen', return_value=io.BytesIO(raw)):
                    with self.assertRaises(at.BibliographicLookupError) as caught:
                        getter('https://example.test/works')
                self.assertEqual(caught.exception.code, 'malformed_response')

    def test_external_payload_shapes(self):
        cases = [
            (at.search_openalex, [[], {}, {'results': {}}, {'results': [None]},
                {'results': [{'authorships': [None]}]},
                {'results': [{'primary_location': {'source': []}}]}]),
            (at.search_crossref, [[], {}, {'message': []}, {'message': {}},
                {'message': {'items': [None]}},
                {'message': {'items': [{'title': 'not an array'}]}},
                {'message': {'items': [{'author': [None]}]}},
                {'message': {'items': [{'issued': None}]}},
                {'message': {'items': [{'issued': {'date-parts': [2024]}}]}}]),
        ]
        for call, payloads in cases:
            for payload in payloads:
                with self.subTest(call=call.__name__, payload=payload):
                    with patch.object(at, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
                        with self.assertRaises(at.BibliographicLookupError) as caught:
                            call('Title')
                    self.assertEqual(caught.exception.code, 'malformed_response')

    def test_empty_searches_and_doi_not_found(self):
        for call, payload in [(at.search_openalex, {'results': []}),
                              (at.search_crossref, {'message': {'items': []}})]:
            with patch.object(at, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
                self.assertEqual(call('Title'), [])
        for call in [at.resolve_doi, at.resolve_openalex_doi]:
            error = HTTPError('https://example.test', 404, 'Not Found', {}, None)
            with patch.object(at, 'urlopen', side_effect=error) as transport:
                self.assertIsNone(call('10.1000/test'))
            transport.assert_called_once()

    def test_doi_operation_metadata(self):
        for service, call in [('crossref', at.resolve_doi), ('openalex', at.resolve_openalex_doi)]:
            with patch.object(at, 'urlopen', side_effect=HTTPError('u', 500, 'Error', {}, None)):
                with self.assertRaises(at.BibliographicLookupError) as caught:
                    call('10.1000/test')
            self.assertEqual((caught.exception.service, caught.exception.operation), (service, 'doi_lookup'))

    def test_transient_retry_semantics(self):
        for service, getter, statuses in [('openalex', at._get_openalex_json, [429, 503]),
                                         ('crossref', at._get_json, [429])]:
            for status in statuses:
                error = HTTPError('u', status, 'Unavailable', {}, None)
                with patch.object(at, 'urlopen', side_effect=error) as transport, patch.object(at.time, 'sleep') as sleep:
                    with self.assertRaises(at.BibliographicLookupError) as caught:
                        getter('https://example.test/works', max_attempts=3)
                self.assertEqual(transport.call_count, 3)
                self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])
                self.assertEqual(caught.exception.http_status, status)
                self.assertEqual(isinstance(caught.exception, at.OpenAlexUnavailableError), service == 'openalex')
        self.assertIsInstance(at.OpenAlexUnavailableError('legacy constructor'), RuntimeError)

    def test_local_errors_propagate(self):
        for error in [TypeError('local'), AttributeError('local'), AssertionError('local'), RuntimeError('local')]:
            for getter in [at._get_json, at._get_openalex_json]:
                with patch.object(at, 'urlopen', side_effect=error):
                    with self.assertRaises(type(error)) as caught:
                        getter('https://example.test/works')
                self.assertIs(caught.exception, error)
        with patch.object(at, 'urlopen', return_value=io.BytesIO(b'{"results": [{}]}')), patch.object(at, '_extract_openalex_candidate', side_effect=TypeError('local parser bug')):
            with self.assertRaises(TypeError):
                at.search_openalex('Title')

    def test_issues_and_unavailable_serialization(self):
        verification = at.VerificationResult(at.VERIFICATION_STATUS_UNAVAILABLE, None, ['Unavailable'])
        self.assertEqual(verification.to_dict()['status'], 'unavailable')
        self.assertFalse(verification.claim_verified)
        issues = [at.BibliographicIssue('title_corroboration', 'openalex', 'unavailable', 'http_error', 503),
                  at.BibliographicIssue('title_corroboration', 'openalex', 'skipped', 'unsafe_title_query')]
        result = at.AcademicReferenceResult(verification, None, None, False, [], 'unavailable', issues=issues)
        payload = json.loads(json.dumps(result.to_dict()))
        self.assertEqual([at.BibliographicIssue(**x) for x in payload['issues']], issues)
        self.assertNotIn('http_status', payload['issues'][1])
        self.assertEqual(set(payload['issues'][0]), {'stage', 'service', 'outcome', 'code', 'http_status'})
        self.assertEqual(orchestrator.resolve_retrieval_identity(result).status, 'not_eligible')
        proposal = orchestrator.VerifiedReferenceProposal(
            academic_chat.AcademicReference('Title', None, None, None, None), result)
        self.assertEqual(proposal.to_dict()['verification']['issues'], payload['issues'])

    def test_successful_adapter_parsing(self):
        cases = [
            (at.search_crossref, {'message': {'items': [{
                'title': ['Title'], 'DOI': '10.1000/test',
                'author': [{'given': 'Ada', 'family': 'Example'}],
                'issued': {'date-parts': [[2024]]}}]}}, 'crossref'),
            (at.search_openalex, {'results': [{
                'title': 'Title', 'doi': 'https://doi.org/10.1000/test',
                'authorships': [{'author': {'display_name': 'Ada Example'}}],
                'publication_year': 2024}]}, 'openalex'),
        ]
        for call, payload, service in cases:
            with patch.object(at, 'urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
                candidate, = call('Title')
            self.assertEqual((candidate.title, candidate.doi, candidate.authors,
                              candidate.year, candidate.source, candidate.title_similarity),
                             ('Title', '10.1000/test', ['Ada Example'], 2024, service, 1.0))

    def test_no_issue_output_unchanged(self):
        result = at.AcademicReferenceResult(at.VerificationResult('verified', None, []), None, None, False, [])
        expected = {
            'crossref_verification': {'status': 'verified', 'candidate': None,
                'reasons': [], 'claim_verified': False, 'related_candidate': None},
            'doi_corroboration': None, 'related_corroboration': None,
            'identity_conflict': False, 'reasons': [],
            'corroboration_status': 'complete', 'claim_verified': False,
        }
        self.assertEqual(result.to_dict(), expected)

    def test_typed_failure_is_contained_at_reference_boundary(self):
        with patch.object(at, 'verify_reference', return_value=at.VerificationResult('verified', None, [])), patch.object(at, '_crossref_candidates', return_value=[]), patch.object(at, 'urlopen', side_effect=HTTPError('u', 400, 'Bad Request', {}, None)):
            result = at.verify_academic_reference(title='Title')
            self.assertEqual(result.corroboration_status, 'unavailable')
            self.assertEqual(result.issues[0].http_status, 400)


if __name__ == '__main__':
    unittest.main()
