"""Offline transport, provenance and reader contracts for deliberate title skips."""
import io
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import academic_chat as chat
import academic_claims as claims
import academic_orchestrator as orchestration
import academic_tools as tools


class TitlePreflightTests(unittest.TestCase):
    def test_safe_titles_preserve_text_at_transport(self):
        for title in ['Statistical power analysis', '  Ordinary  WORDS 2026  ', 'ORbit ANDerson NOTable', '123']:
            with patch.object(tools, 'urlopen', return_value=io.BytesIO(b'{"results": []}')) as transport:
                self.assertEqual(tools.search_openalex(title), [])
            request = transport.call_args.args[0]
            self.assertEqual(parse_qs(urlsplit(request.full_url).query), {
                'filter': ['title.search:' + title.strip()], 'per-page': ['5']})

    def test_unsafe_titles_never_reach_transport(self):
        titles = ['Statistical power, analysis', 'A "quoted" title', "Fisher's test",
                  'A|B', 'A*', 'Why?', 'A: B', 'A; B', 'A & B', 'A+B', '95%',
                  '(A)', '[A]', 'A/B', 'A\\B', 'Café', '日本語', 'A\nB', 'A\tB',
                  'A\x00B', 'A AND B', 'A or B', 'not A', '', '   ', 'A' * 3000]
        for title in titles:
            with self.subTest(title=title), patch.object(tools, 'urlopen') as transport:
                self.assertFalse(tools.is_safe_openalex_title(title))
                with self.assertRaises(tools.UnsafeOpenAlexTitleQuery):
                    tools.search_openalex(title)
                transport.assert_not_called()
        self.assertFalse(issubclass(tools.UnsafeOpenAlexTitleQuery, tools.BibliographicLookupError))

    def test_exact_length_boundary_and_page_bounds(self):
        overhead = len(tools.OPENALEX_API + '/works?filter=title.search%3A&per-page=5')
        title = 'A' * (tools.OPENALEX_TITLE_URL_MAX_BYTES - overhead)
        self.assertTrue(tools.is_safe_openalex_title(title))
        self.assertFalse(tools.is_safe_openalex_title(title + 'A'))
        for rows, expected in [(-1, '1'), (999, '25')]:
            with patch.object(tools, 'urlopen', return_value=io.BytesIO(b'{"results": []}')) as transport:
                tools.search_openalex('Title', rows=rows)
            self.assertEqual(parse_qs(urlsplit(transport.call_args.args[0].full_url).query)['per-page'], [expected])

    def test_programming_errors_still_propagate(self):
        verification = tools.VerificationResult('verified', None, [])
        for error in [RuntimeError('local bug'), TypeError('local bug')]:
            with patch.object(tools, 'verify_reference', return_value=verification), patch.object(tools, '_crossref_candidates', return_value=[]), patch.object(tools, '_get_openalex_json', side_effect=error):
                with self.assertRaises(type(error)) as caught:
                    tools.verify_academic_reference(title='Safe Title')
                self.assertIs(caught.exception, error)
        with patch.object(tools, 'verify_reference', side_effect=RuntimeError('Crossref failure')):
            with self.assertRaises(RuntimeError):
                tools.verify_academic_reference(title='Unsafe, Title')

    def test_completed_evidence_and_other_reference_survive(self):
        unsafe = '  Statistical power, analysis  '
        safe = 'Safe Title'
        def candidate(title):
            return tools.ReferenceCandidate(title, ['Ada'], 2024, 'Journal',
                '10.1000/unsafe' if title == unsafe else '10.1000/safe', 'article', title_similarity=1.0)
        verified = {title: tools.VerificationResult('verified', candidate(title), ['Completed Crossref']) for title in [unsafe, safe]}
        refs = [chat.AcademicReference(title, 'Ada', 2024, 'Journal', candidate(title).doi) for title in [unsafe, safe]]
        draft = chat.AcademicDraft('An answer.', refs, [chat.SourceClaim('First claim', 0), chat.SourceClaim('Second claim', 1)], [])
        discover = Mock(side_effect=lambda doi: claims.SourceLocation('location_not_found', doi, 'openalex', None, None, False, []))
        retrieve, locate, assess = Mock(), Mock(), Mock()
        work = {'title': safe, 'doi': 'https://doi.org/10.1000/safe', 'publication_year': 2024,
                'authorships': [{'author': {'display_name': 'Ada'}}], 'primary_location': {'source': {'display_name': 'Journal'}}}
        with patch.object(tools, 'verify_reference', side_effect=lambda **kw: verified[kw['title']]), patch.object(tools, '_crossref_candidates', side_effect=lambda title, **kw: [candidate(title)]), patch.object(tools, 'resolve_doi', side_effect=lambda doi: candidate(unsafe if doi.endswith('unsafe') else safe)), patch.object(tools, 'resolve_openalex_doi', side_effect=lambda doi: candidate(unsafe if doi.endswith('unsafe') else safe)), patch.object(tools, 'urlopen', return_value=io.BytesIO(json.dumps({'results': [work]}).encode())) as transport:
            result = orchestration.assess_academic_draft(draft,
                local_guidance=orchestration.LocalGuidanceResult([]),
                source_discoverer=discover, source_retriever=retrieve,
                claim_locator=locate, claim_assessor=assess)
        transport.assert_called_once()
        self.assertEqual(parse_qs(urlsplit(transport.call_args.args[0].full_url).query)['filter'], ['title.search:Safe Title'])
        first, second = result.references
        self.assertEqual(first.proposed_reference.title, unsafe)
        self.assertEqual(first.to_dict()['proposed_reference']['title'], unsafe)
        self.assertIs(first.verification.crossref_verification, verified[unsafe])
        self.assertEqual(first.verification.doi_corroboration.status, 'corroborated')
        self.assertEqual(first.verification.corroboration_status, 'unavailable')
        self.assertIsNone(first.verification.related_corroboration)
        self.assertEqual(first.verification.to_dict()['issues'], [{
            'stage': 'title_corroboration', 'service': 'openalex',
            'outcome': 'skipped', 'code': 'unsafe_title_query'}])
        blocked = result.source_claims[0]
        self.assertEqual(blocked.retrieval_identity.status, 'not_eligible')
        self.assertIsNone(blocked.retrieval_identity.doi)
        self.assertEqual(blocked.source_discovery.status, 'not_attempted')
        self.assertIsNone(blocked.source_retrieval)
        self.assertIsNone(blocked.claim_assessment)
        self.assertEqual(second.verification.corroboration_status, 'complete')
        self.assertEqual(result.source_claims[1].retrieval_identity.status, 'eligible')
        discover.assert_called_once_with('10.1000/safe')
        retrieve.assert_not_called(); locate.assert_not_called(); assess.assert_not_called()

    @unittest.skipUnless(shutil.which('node'), 'Node required for real reference renderer')
    def test_reader_skip_is_not_an_outage(self):
        html = (Path(__file__).resolve().parents[1] / 'app/chat.html').read_text()
        functions = '\n'.join(re.findall(r'^function \w+\(.*?\n}\n', html, re.S | re.M))
        payload = {'proposed_reference': {'title': 'Unsafe, Title'}, 'verification': {
            'crossref_verification': {'status': 'verified', 'candidate': {'title': 'Unsafe, Title'}},
            'corroboration_status': 'unavailable', 'issues': [{
                'service': 'openalex', 'stage': 'title_corroboration', 'outcome': 'skipped', 'code': 'unsafe_title_query'}]}}
        script = functions + '\nprocess.stdout.write(renderAcademicReference(' + json.dumps(payload) + ', 0));'
        run = subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
        self.assertIn('Title corroboration not attempted', run.stdout)
        self.assertIn('Bibliographic identity verified', run.stdout)
        self.assertNotIn('OpenAlex was unavailable', run.stdout)
        self.assertNotIn('Retry Academic Chat', run.stdout)
        self.assertNotIn('no matching record', run.stdout)


if __name__ == '__main__':
    unittest.main()
