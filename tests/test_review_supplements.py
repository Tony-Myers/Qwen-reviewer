"""Offline Review supplement regressions: uploads, provenance and evidence use."""
import asyncio
import io
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
import server
import review_pipeline as rp

PRIMARY = 'The primary outcome was measured after twelve weeks of treatment.'
SUPPLEMENT = 'The sensitivity analysis used complete cases and robust standard errors.'
REPORT = ('# Overall synopsis\nA primary manuscript with supporting evidence.\n'
          '# Major strengths\nClear reporting.\n# Directly supported concerns\n'
          '* Concern: Check the sensitivity analysis.\n'
          f'* Evidence: "{SUPPLEMENT}"\n'
          '# Verification prompts\nCheck the design.\n# Extraction limits\nText only.\n'
          '# Overall confidence\nModerate.\n')


class Supplements(unittest.TestCase):
    def setUp(self):
        self.jobs = patch.object(server, 'review_jobs', {})
        self.jobs.start()
        self.addCleanup(self.jobs.stop)

    def upload(self, name, body=b'text'):
        return UploadFile(filename=name, file=io.BytesIO(body))

    def start(self, supplements=(), primary=b'main'):
        return asyncio.run(server.start_review(
            file=self.upload('../main.txt', primary), supplements=list(supplements),
            domain='general', thinking='', vision=''))

    def test_uploads_paths_duplicates_and_total_limit(self):
        with patch.object(server.threading, 'Thread') as thread:
            result = self.start([self.upload('../../same.txt'), self.upload('/tmp/same.txt')])
            args = thread.call_args.kwargs['args']
            root = args[3]
            self.addCleanup(server.shutil.rmtree, root, True)
            job = server.review_jobs[result['job_id']]
            self.assertEqual(args[1].name, 'upload.txt')
            paths = [Path(x['path']) for x in job['supplements']]
            self.assertEqual(len(set(paths)), 2)
            self.assertTrue(all(p.parent == root and p.is_file() for p in paths))
            self.assertEqual([x['name'] for x in job['supplements']], ['same.txt', 'same.txt'])
        with patch.object(server, 'MAX_REVIEW_UPLOAD_BYTES', 8), patch.object(server.threading, 'Thread'):
            accepted = self.start([self.upload('s.txt', b'abcd')], primary=b'abcd')
            root = Path(server.review_jobs[accepted['job_id']]['supplements'][0]['path']).parent
            self.addCleanup(server.shutil.rmtree, root, True)
            made = []
            original = tempfile.mkdtemp
            def create(**kw):
                path = original(**kw); made.append(Path(path)); return path
            with patch.object(server.tempfile, 'mkdtemp', side_effect=create):
                with self.assertRaises(HTTPException) as caught:
                    self.start([self.upload('s.txt', b'abcde')], primary=b'abcd')
            self.assertEqual(caught.exception.status_code, 413)
            self.assertTrue(all(not p.exists() for p in made))

    def test_reject_type_before_storage_and_failed_write_cleanup(self):
        with patch.object(server.tempfile, 'mkdtemp') as create:
            with self.assertRaises(HTTPException) as caught:
                self.start([self.upload('supp.exe')])
            self.assertEqual(caught.exception.status_code, 400)
            create.assert_not_called()
        class Broken(io.BytesIO):
            def read(self, *a): raise OSError('read failed')
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer) / 'upload'; root.mkdir()
            with patch.object(server.tempfile, 'mkdtemp', return_value=str(root)):
                with self.assertRaises(OSError):
                    self.start([UploadFile(filename='s.txt', file=Broken())])
            self.assertFalse(root.exists())

    def test_multipart_optional_and_multiple(self):
        with patch.object(server, 'ensure_model'), \
             patch.object(server.threading, 'Thread') as thread, TestClient(server.app) as client:
            for count in (0, 1, 2):
                files = [('file', ('main.txt', b'main', 'text/plain'))]
                files += [('supplements', (f's{i}.txt', b'evidence', 'text/plain')) for i in range(count)]
                response = client.post('/api/review', files=files)
                self.assertEqual(response.status_code, 200, response.text)
                args = thread.call_args.kwargs['args']
                self.addCleanup(server.shutil.rmtree, args[3], True)
                self.assertEqual(len(server.review_jobs[response.json()['job_id']]['supplements']), count)

    def run_worker(self, count, cancel=False):
        root = Path(tempfile.mkdtemp())
        path = root / 'upload.txt'; path.write_text(PRIMARY)
        supplements = []
        for i in range(count):
            p = root / f's{i}.txt'; p.write_text(SUPPLEMENT + f' Source marker {i}.')
            supplements.append({'path': str(p), 'name': 'same.txt'})
        job = dict(status='running', progress=[], filename='main.txt', supplements=supplements,
                   cancel_requested=False, thinking=None, thinking_scope='review')
        server.review_jobs['test'] = job
        chunks, summaries, syntheses = [], [], []
        def chunk(model, tokenizer, chunk, **kw):
            chunks.append((chunk, kw))
            if cancel and chunk.source_name.startswith('Supplement'):
                job['cancel_requested'] = True
            return chunk.text
        def summary(model, tokenizer, name, combined, **kw):
            summaries.append((name, kw)); return combined
        def synthesis(model, tokenizer, files, **kw):
            syntheses.append((files, kw)); return REPORT
        with ExitStack() as stack:
            for name, value in [('review_chunk', chunk), ('synthesize_file_review', summary),
                                ('synthesize_report', synthesis),
                                ('validate_report_against_evidence', lambda m,t,d,f,**kw: d)]:
                stack.enter_context(patch.object(rp, name, side_effect=value))
            stack.enter_context(patch.object(rp, 'REVIEW_PASSES', 1))
            server._run_review_inner('test', path, 'general', root)
        self.assertFalse(root.exists())
        return job, chunks, summaries, syntheses

    def test_pipeline_zero_one_multiple(self):
        for count in (0, 1, 2):
            with self.subTest(count=count):
                job, chunks, summaries, syntheses = self.run_worker(count)
                self.assertEqual(job['status'], 'complete', job.get('error'))
                self.assertEqual(len(chunks), count + 1)
                files, options = syntheses[0]
                self.assertEqual(len(files), count + 1)
                if not count:
                    self.assertNotIn('primary_source', options)
                    self.assertNotIn('sources', job)
                    self.assertEqual(chunks[0][0].source_name, 'upload.txt')
                else:
                    self.assertEqual(options['primary_source'], 'Primary manuscript: main.txt')
                    names = [chunk.source_name for chunk, _ in chunks]
                    self.assertEqual(len(set(names)), count + 1)
                    self.assertEqual(list(job['sources']), names)
                    self.assertEqual(job['appendix'].count('# Evidence appendix'), 1)
                    for manifest in options['all_manifests']:
                        self.assertTrue(all(b.source_name == manifest.source_name for b in manifest.blocks))
                    for name in names:
                        self.assertIn(name, job['report'])
                        self.assertIn(name, job['appendix'])
                    for _, kw in chunks:
                        self.assertIn('not separate manuscripts', kw['method_expectations'])
                    self.assertIn('Quotation source locations', job['report'])
                    self.assertIn('Supplement 1: same.txt', job['report'])
                    self.assertEqual(job['text'], PRIMARY)

    def test_cancel_during_supplement_cleans_all_files(self):
        job, chunks, summaries, syntheses = self.run_worker(2, cancel=True)
        self.assertEqual(job['status'], 'cancelled')
        self.assertEqual(len(chunks), 2)
        self.assertEqual(syntheses, [])

    def test_quotes_resolve_within_individual_sources(self):
        sources = {'Primary manuscript: main.txt': PRIMARY, 'Supplement 1: s.txt': SUPPLEMENT}
        for text, name in [(PRIMARY, 'Primary manuscript: main.txt'), (SUPPLEMENT, 'Supplement 1: s.txt')]:
            report = f'Evidence: "{text}"'
            self.assertEqual(rp.verify_report_citations(report, sources), [])
            self.assertEqual(rp.mark_unverified_quotations(report, sources), report)
            self.assertIn(name, rp.format_quote_sources(report, sources))
            self.assertEqual(rp.concern_confidence(report, sources)[0], 'High')
        fabricated = f'"{PRIMARY} ... {SUPPLEMENT}"'
        self.assertTrue(rp.verify_report_citations(fabricated, sources))
        self.assertEqual(rp.quotation_sources(PRIMARY + ' ... ' + SUPPLEMENT, sources), [])
        self.assertIn('not verbatim', rp.mark_unverified_quotations(fabricated, sources))
        self.assertNotEqual(rp.concern_confidence(fabricated, sources)[0], 'High')

    def test_qa_retrieves_and_attributes_supplement(self):
        sources = {'Primary manuscript: main.txt': PRIMARY, 'Supplement 1: s.txt': SUPPLEMENT}
        hits = rp.select_source_passages('sensitivity analysis', sources, 180)
        self.assertTrue(any(name.startswith('Supplement') for name, _, _ in hits))
        prompts = []
        with patch.object(rp, 'apply_chat_template_compat', side_effect=lambda t,p: prompts.append(p) or p), \
             patch.object(rp, 'generate', return_value=f'"{SUPPLEMENT}"'), \
             patch.object(rp, 'make_default_sampler', return_value=None):
            answer, problems = rp.answer_manuscript_question(None, None, 'sensitivity?', PRIMARY, sources=sources)
        self.assertEqual(problems, [])
        self.assertIn('Source: Supplement 1: s.txt', prompts[0])
        self.assertIn('Source: Primary manuscript: main.txt', prompts[0])
        self.assertIn('Supplement 1: s.txt', answer)
        server.review_jobs['qa'] = dict(status='complete', text=PRIMARY, report='', sources=sources)
        with patch.object(server, 'ensure_model'), patch.object(rp, 'answer_manuscript_question', return_value=(answer, [])) as ask:
            response = asyncio.run(server.ask_about_review('qa', {'question': 'sensitivity?'}))
        self.assertEqual(ask.call_args.kwargs['sources'], sources)
        self.assertIn('Supplement 1: s.txt', str(response['provenance']))

    def test_extraction_failure_and_thread_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as outer:
            root = Path(outer) / 'files'; root.mkdir()
            primary = root / 'upload.txt'; primary.write_text(PRIMARY)
            supplement = root / 's.txt'; supplement.write_text('unreadable')
            server.review_jobs['failed'] = dict(status='running', progress=[], filename='main.txt',
                supplements=[{'path': str(supplement), 'name': 's.txt'}])
            real_load = rp.load_document
            def load(path):
                if path == supplement:
                    raise ValueError('supplement extraction failed')
                return real_load(path)
            with patch.object(rp, 'load_document', side_effect=load), \
                 patch.object(rp, 'review_chunk', return_value='notes'), \
                 patch.object(rp, 'synthesize_file_review', return_value='summary'):
                server._run_review_inner('failed', primary, 'general', root)
            self.assertEqual(server.review_jobs['failed']['status'], 'error')
            self.assertIn('supplement extraction failed', server.review_jobs['failed']['error'])
            self.assertFalse(root.exists())
            root.mkdir()
            with patch.object(server.tempfile, 'mkdtemp', return_value=str(root)), \
                 patch.object(server.threading, 'Thread', side_effect=RuntimeError('thread failed')):
                with self.assertRaises(RuntimeError):
                    self.start([self.upload('s.txt')])
            self.assertFalse(root.exists())
            self.assertEqual(set(server.review_jobs), {'failed'})

    def test_ui_separate_optional_multiple_control(self):
        html = (Path(server.__file__).parent / 'chat.html').read_text()
        import re
        primary = re.search(r'<input[^>]*id="fileInput"[^>]*>', html).group()
        supplement = re.search(r'<input[^>]*id="supplementInput"[^>]*>', html).group()
        self.assertNotIn('multiple', primary)
        self.assertIn('multiple', supplement)
        self.assertNotIn('required', supplement)
        self.assertIn("fd.append('file', selectedFile)", html)
        self.assertIn("fd.append('supplements', supplement)", html)
        self.assertIn('100 MiB total across all files', html)

    def test_role_contract_reaches_synthesis_and_validation(self):
        prompts=[]
        with patch.object(rp, 'apply_chat_template_compat', side_effect=lambda t,p: prompts.append(p) or p), \
             patch.object(rp, 'generate', return_value=REPORT), \
             patch.object(rp, 'make_default_sampler', return_value=None):
            rp.synthesize_report(None,None,[('main','main text'),('supp','supp text')],primary_source='main')
            rp.validate_report_against_evidence(None,None,REPORT,[('main','main text'),('supp','supp text')],primary_source='main')
        self.assertEqual(len(prompts),2)
        for prompt in prompts:
            self.assertIn('sole manuscript being critically appraised is main',prompt)
            self.assertIn('appropriately supplied in supplements',prompt)
            self.assertIn('# File: supp',prompt)


if __name__ == '__main__': unittest.main()
