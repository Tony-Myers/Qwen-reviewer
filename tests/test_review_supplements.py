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

    def test_review_trace_is_observational(self):
        root = Path(tempfile.mkdtemp())
        path = root / 'upload.txt'
        path.write_text(PRIMARY)

        server.review_jobs['trace-test'] = dict(
            status='running',
            progress=[],
            filename='main.txt',
            supplements=[],
            cancel_requested=False,
            thinking=None,
            thinking_scope='review',
        )

        raw_draft = REPORT.replace(
            'Check the sensitivity analysis.',
            'RAW synthesis concern.',
        )
        validated_draft = raw_draft.replace(
            'RAW synthesis concern.',
            'VALIDATED synthesis concern.',
        )
        merged_draft = validated_draft.replace(
            'VALIDATED synthesis concern.',
            'MERGED synthesis concern.',
        )

        merge_inputs = []

        triage_calls = []
        proposition_calls = []
        verification_calls = []
        proposition_result = {
            "assessment_type": "whole_file_methodological_propositions",
            "propositions": [
                {
                    "proposition_id": "method-proposition-1",
                    "proposition": (
                        "The shared-control structure has a methodological "
                        "implication requiring whole-file consideration."
                    ),
                    "candidate_ids": [
                        "primary.pdf:chunk-1:candidate-2",
                    ],
                    "state": "unresolved_question",
                    "reason": (
                        "This proposition is constructed from the existing "
                        "candidate ledger and whole-file evidence."
                    ),
                }
            ],
            "resolved_candidate_groups": [],
            "represented_candidate_ids": [
                "primary.pdf:chunk-1:candidate-2",
            ],
            "resolved_candidate_ids": [],
        }
        verification_result = {
            "assessment_type": "whole_file_proposition_verification",
            "verifications": [
                {
                    "proposition_id": "method-proposition-1",
                    "verdict": "keep",
                    "verified_proposition": (
                        "The shared-control structure has a methodological "
                        "implication requiring whole-file consideration."
                    ),
                    "verified_state": "unresolved_question",
                    "counterevidence_check": (
                        "Whole-file positive evidence was checked and does "
                        "not resolve the proposition."
                    ),
                    "reason": (
                        "The proposition remains grounded after whole-file "
                        "verification."
                    ),
                }
            ],
        }
        triage_result = {
            "assessment_type": "whole_file_candidate_triage",
            "themes": [
                {
                    "theme": "Shared-control dependence requires scrutiny.",
                    "candidate_ids": [
                        "primary.pdf:chunk-1:candidate-2",
                    ],
                    "state": "concern_candidate",
                    "priority": "high",
                    "reason": "Methodologically consequential candidate.",
                }
            ],
            "retained_candidate_ids": [
                "primary.pdf:chunk-1:candidate-2",
            ],
            "omitted_candidate_ids": [
                "primary.pdf:chunk-1:candidate-1",
            ],
        }

        def propositions(candidates, manuscript_text, assessor, **kw):
            proposition_calls.append({
                "candidates": list(candidates),
                "manuscript_text": manuscript_text,
                "kwargs": dict(kw),
            })
            return proposition_result

        def verify(propositions, manuscript_text, assessor, **kw):
            verification_calls.append({
                "propositions": propositions,
                "manuscript_text": manuscript_text,
                "kwargs": dict(kw),
            })
            return verification_result

        def triage(candidates, manuscript_text, assessor, **kw):
            triage_calls.append({
                "candidates": list(candidates),
                "manuscript_text": manuscript_text,
                "kwargs": dict(kw),
            })
            return triage_result

        def file_synthesis(model, tokenizer, file_name, combined, **kw):
            self.assertNotIn("candidate_propositions", kw)
            self.assertNotIn("propositions", kw)
            self.assertNotIn("candidate_proposition_verification", kw)
            self.assertNotIn("proposition_verification", kw)
            self.assertNotIn("candidate_triage", kw)
            self.assertNotIn("triage", kw)
            return "file summary"

        def synthesis(model, tokenizer, files, **kw):
            return raw_draft

        def validate(model, tokenizer, draft, files, **kw):
            self.assertEqual(draft, raw_draft)
            return validated_draft

        def merge(drafts, **kw):
            merge_inputs.append(list(drafts))
            return merged_draft

        with ExitStack() as stack:
            chunk_review = '''## Supported points
- This supported point must not enter the candidate ledger.

## Reasonable inferences
- This inference must not enter the candidate ledger.

## Missing or unclear
- Priors are not described.

## Statistical / methodological concerns
- Multi-arm trials are treated as independent samples.
  Verify whether shared-control correlation is accounted for.
'''
            stack.enter_context(patch.object(rp, 'review_chunk', return_value=chunk_review))
            stack.enter_context(
                patch.object(
                    rp,
                    'generate_candidate_propositions',
                    side_effect=propositions,
                )
            )
            stack.enter_context(
                patch.object(
                    rp,
                    'verify_candidate_propositions',
                    side_effect=verify,
                )
            )
            stack.enter_context(patch.object(rp, 'triage_candidate_findings', side_effect=triage))
            stack.enter_context(patch.object(rp, 'synthesize_file_review', side_effect=file_synthesis))
            stack.enter_context(patch.object(rp, 'synthesize_report', side_effect=synthesis))
            stack.enter_context(patch.object(rp, 'validate_report_against_evidence', side_effect=validate))
            stack.enter_context(patch.object(rp, 'merge_reports', side_effect=merge))
            stack.enter_context(patch.object(rp, 'REVIEW_PASSES', 1))

            server._run_review_inner('trace-test', path, 'general', root)

        job = server.review_jobs['trace-test']
        self.assertEqual(job['status'], 'complete', job.get('error'))

        trace = job['trace']
        self.assertIsNotNone(trace)

        self.assertEqual(len(trace['files']), 1)
        self.assertEqual(
            trace['files'][0]['source_chunks'],
            rp.split_text(PRIMARY),
        )
        self.assertEqual(trace['files'][0]['chunk_outputs'], [chunk_review])
        self.assertEqual(trace['files'][0]['file_summary'], 'file summary')

        candidates = trace['files'][0]['candidate_findings']
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]['section'], 'missing or unclear')
        self.assertIn('Priors are not described', candidates[0]['text'])
        self.assertEqual(
            candidates[1]['section'],
            'statistical / methodological concerns',
        )
        self.assertIn('Multi-arm trials', candidates[1]['text'])
        self.assertIn('shared-control correlation', candidates[1]['text'])
        candidate_text = '\n'.join(item['text'] for item in candidates)
        self.assertNotIn('supported point', candidate_text)
        self.assertNotIn('inference must not enter', candidate_text)

        self.assertEqual(len(proposition_calls), 1)
        self.assertEqual(
            proposition_calls[0]['candidates'],
            candidates,
        )
        self.assertTrue(proposition_calls[0]['manuscript_text'])

        self.assertEqual(len(verification_calls), 1)
        self.assertIs(
            verification_calls[0]['propositions'],
            proposition_result,
        )
        self.assertEqual(
            verification_calls[0]['manuscript_text'],
            proposition_calls[0]['manuscript_text'],
        )

        file_trace = trace['files'][0]
        self.assertEqual(
            file_trace['candidate_proposition_verification'],
            verification_result,
        )
        self.assertEqual(
            file_trace['candidate_proposition_verification_error'],
            '',
        )

        self.assertEqual(len(triage_calls), 1)
        self.assertEqual(
            triage_calls[0]['candidates'],
            candidates,
        )
        self.assertEqual(
            triage_calls[0]['manuscript_text'],
            proposition_calls[0]['manuscript_text'],
        )
        self.assertTrue(triage_calls[0]['manuscript_text'])

        # Both observational structured stages must see exactly the same
        # application-bounded whole-file manuscript evidence.
        self.assertEqual(
            proposition_calls[0]['manuscript_text'],
            triage_calls[0]['manuscript_text'],
        )

        # Proposition output remains trace-only: it is not supplied to the
        # existing triage call.
        self.assertNotIn(
            "candidate_propositions",
            triage_calls[0]['kwargs'],
        )
        self.assertNotIn(
            "propositions",
            triage_calls[0]['kwargs'],
        )

        self.assertEqual(
            trace['files'][0]['candidate_propositions'],
            proposition_result,
        )
        self.assertEqual(
            trace['files'][0]['candidate_propositions_error'],
            '',
        )
        self.assertEqual(
            trace['files'][0]['candidate_triage'],
            triage_result,
        )
        self.assertEqual(
            trace['files'][0]['candidate_triage_error'],
            '',
        )
        self.assertIsNotNone(
            trace['files'][0]['candidate_triage_budget'],
        )

        self.assertEqual(len(trace['final_synthesis']), 1)
        stage = trace['final_synthesis'][0]
        self.assertEqual(stage['raw'], raw_draft)
        self.assertEqual(stage['validated'], validated_draft)

        self.assertEqual(merge_inputs, [[validated_draft]])
        self.assertEqual(trace['merged_pre_postprocessing'], merged_draft)

        self.assertEqual(trace['final_report'], job['report'])
        self.assertNotEqual(
            trace['merged_pre_postprocessing'],
            trace['final_report'],
        )

    def test_candidate_finding_extraction_preserves_multiline_items(self):
        review = '''## Supported points
- Do not retain this.

## Reasonable inferences
- Do not retain this either.

## Missing or unclear
- **Priors:** Prior distributions are not described.
  This continuation belongs to the same candidate.

## Statistical / methodological concerns
- **Multi-arm trials:** Arms are described as independent samples.
  Verify whether shared-control correlation is accounted for.
- **Missing data:** Mean substitution may underestimate uncertainty.

## Table-specific notes
- **Table S9:** Several coefficients require clarification.

## Questions raised by this chunk
- How were moderator variables centred and scaled?
'''
        got = rp.extract_candidate_findings(
            review,
            source_name='paper.pdf',
            chunk_id=7,
        )

        self.assertEqual(len(got), 5)
        self.assertEqual(
            [item['section'] for item in got],
            [
                'missing or unclear',
                'statistical / methodological concerns',
                'statistical / methodological concerns',
                'table-specific notes',
                'questions raised by this chunk',
            ],
        )
        self.assertTrue(all(item['source_name'] == 'paper.pdf' for item in got))
        self.assertTrue(all(item['chunk_id'] == 7 for item in got))
        self.assertTrue(all(item['status'] == 'candidate' for item in got))
        self.assertIn('continuation belongs', got[0]['text'])
        self.assertIn('shared-control correlation', got[1]['text'])

        candidate_text = '\n'.join(item['text'] for item in got)
        self.assertNotIn('Do not retain this.', candidate_text)
        self.assertNotIn('Do not retain this either.', candidate_text)
        self.assertEqual(
            len({item['candidate_id'] for item in got}),
            len(got),
        )

    def test_candidate_grouping_is_lossless_and_conservative(self):
        candidates = [
            {
                "candidate_id": "paper:chunk-1:candidate-1",
                "source_name": "paper",
                "chunk_id": 1,
                "section": "statistical / methodological concerns",
                "text": "- Missing intensity values were mean substituted.",
                "status": "candidate",
            },
            {
                "candidate_id": "paper:chunk-2:candidate-1",
                "source_name": "paper",
                "chunk_id": 2,
                "section": "table-specific notes",
                "text": "*   Missing intensity values were mean substituted. ",
                "status": "candidate",
            },
            {
                "candidate_id": "paper:chunk-3:candidate-1",
                "source_name": "paper",
                "chunk_id": 3,
                "section": "statistical / methodological concerns",
                "text": "- Mean substitution may underestimate uncertainty.",
                "status": "candidate",
            },
        ]

        groups = rp.group_candidate_findings(candidates)

        self.assertEqual(len(groups), 2)
        self.assertEqual(
            groups[0]["member_candidate_ids"],
            [
                "paper:chunk-1:candidate-1",
                "paper:chunk-2:candidate-1",
            ],
        )
        self.assertEqual(groups[0]["chunk_ids"], [1, 2])
        self.assertEqual(
            groups[0]["sections"],
            [
                "statistical / methodological concerns",
                "table-specific notes",
            ],
        )
        self.assertEqual(groups[0]["status"], "observational")

        self.assertEqual(
            groups[1]["member_candidate_ids"],
            ["paper:chunk-3:candidate-1"],
        )

        retained = [
            candidate_id
            for group in groups
            for candidate_id in group["member_candidate_ids"]
        ]
        self.assertEqual(
            retained,
            [candidate["candidate_id"] for candidate in candidates],
        )

    def test_candidate_grouping_does_not_merge_related_distinct_findings(self):
        candidates = [
            {
                "candidate_id": "paper:chunk-27:candidate-1",
                "source_name": "paper",
                "chunk_id": 27,
                "section": "statistical / methodological concerns",
                "text": "- Quadratic DIC was 476.3 and spline DIC was 478.2.",
                "status": "candidate",
            },
            {
                "candidate_id": "paper:chunk-28:candidate-1",
                "source_name": "paper",
                "chunk_id": 28,
                "section": "statistical / methodological concerns",
                "text": "- The RE model DIC was 167.791.",
                "status": "candidate",
            },
        ]

        groups = rp.group_candidate_findings(candidates)

        self.assertEqual(len(groups), 2)
        self.assertEqual(
            groups[0]["member_candidate_ids"],
            ["paper:chunk-27:candidate-1"],
        )
        self.assertEqual(
            groups[1]["member_candidate_ids"],
            ["paper:chunk-28:candidate-1"],
        )

    def test_candidate_evidence_assessment_is_bounded_and_app_owned(self):
        candidate = {
            "candidate_id": "paper.pdf:chunk-3:candidate-1",
            "source_name": "paper.pdf",
            "chunk_id": 3,
            "section": "statistical / methodological concerns",
            "text": (
                "- Multi-arm trials are described as treating qualifying "
                "groups as independent samples."
            ),
            "status": "candidate",
        }
        manuscript_chunk = (
            "For studies with three or more groups, qualifying groups were "
            "treated as independent samples."
        )

        captured = {}

        def assessor(*, prompt, schema):
            captured["prompt"] = prompt
            captured["schema"] = schema
            return {
                "evidence_relationship": "supported",
                "reason": (
                    "The supplied manuscript text explicitly states that "
                    "qualifying groups were treated as independent samples."
                ),
            }

        result = rp.assess_candidate_evidence(
            candidate,
            manuscript_chunk,
            assessor,
        )

        self.assertEqual(result["assessment_type"], "factual_evidence")
        self.assertEqual(result["evidence_relationship"], "supported")
        self.assertEqual(result["disposition"], "retained")
        self.assertIn("independent samples", captured["prompt"])
        self.assertIn(manuscript_chunk, captured["prompt"])
        self.assertIn("Do not use outside knowledge.", captured["prompt"])
        self.assertEqual(
            set(captured["schema"]["properties"]),
            {"evidence_relationship", "reason"},
        )

        contradicted = rp.build_candidate_evidence_assessment(
            candidate,
            {
                "evidence_relationship": "contradicted",
                "reason": "The manuscript explicitly states the opposite.",
            },
        )
        self.assertEqual(contradicted["disposition"], "rejected")

        unclear = rp.build_candidate_evidence_assessment(
            candidate,
            {
                "evidence_relationship": "unclear",
                "reason": "The supplied chunk does not establish this point.",
            },
        )
        self.assertEqual(unclear["disposition"], "unresolved")

        with self.assertRaises(ValueError):
            rp.build_candidate_evidence_assessment(
                candidate,
                {
                    "evidence_relationship": "supported",
                    "reason": "Valid reason.",
                    "model_owned_status": "important",
                },
            )

        with self.assertRaises(ValueError):
            rp.build_candidate_evidence_assessment(
                candidate,
                {
                    "evidence_relationship": "verified",
                    "reason": "Invalid relationship.",
                },
            )

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



class DistributedChunkEvidenceTests(unittest.TestCase):
    def test_complete_evidence_is_unchanged_when_it_fits(self):
        chunks = ["alpha", "beta", "gamma"]
        evidence, note = rp.distributed_chunk_evidence(chunks, 100)
        self.assertEqual(evidence, "alpha\n\nbeta\n\ngamma")
        self.assertEqual(note, "")

    def test_trimmed_evidence_preserves_every_chunk_and_both_ends(self):
        chunks = [
            "A-start-" + ("a" * 100) + "-A-end",
            "B-start-" + ("b" * 100) + "-B-end",
            "C-start-" + ("c" * 100) + "-C-end",
        ]
        evidence, note = rp.distributed_chunk_evidence(chunks, 240)

        self.assertLessEqual(len(evidence), 240)
        for i, letter in enumerate("ABC", start=1):
            self.assertIn(f"[Chunk {i}]", evidence)
            self.assertIn(f"{letter}-start-", evidence)
            self.assertIn(f"-{letter}-end", evidence)
        self.assertIn("retained material from all 3 manuscript chunks", note)

    def test_invalid_distributed_evidence_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            rp.distributed_chunk_evidence([], 100)
        with self.assertRaises(ValueError):
            rp.distributed_chunk_evidence(["abc"], 0)


class CandidateTriageBudgetTests(unittest.TestCase):
    def test_prepares_bounded_evidence_and_preserves_all_chunks(self):
        candidates = [
            {
                "candidate_id": "paper:chunk-1:candidate-1",
                "source_name": "paper",
                "chunk_id": 1,
                "section": "missing or unclear",
                "text": "Check the analysis specification.",
                "status": "candidate",
            }
        ]
        chunks = [
            "A-start-" + ("a" * 3000) + "-A-end",
            "B-start-" + ("b" * 3000) + "-B-end",
        ]

        evidence, note, diagnostics = rp.prepare_candidate_triage_evidence(
            candidates,
            chunks,
            minimum_chars_per_chunk=100,
        )

        self.assertIn("A-start-", evidence)
        self.assertIn("-A-end", evidence)
        self.assertIn("B-start-", evidence)
        self.assertIn("-B-end", evidence)
        self.assertLessEqual(
            diagnostics["final_prompt_chars"],
            diagnostics["target_chars"],
        )
        self.assertGreaterEqual(
            diagnostics["remaining_capacity_chars"],
            diagnostics["safety_chars"],
        )

    def test_fails_safely_when_fixed_overhead_squeezes_evidence(self):
        candidates = [
            {
                "candidate_id": f"paper:chunk-1:candidate-{i}",
                "source_name": "paper",
                "chunk_id": 1,
                "section": "missing or unclear",
                "text": "x" * 2000,
                "status": "candidate",
            }
            for i in range(100)
        ]

        with self.assertRaisesRegex(
            ValueError, "exceeds safe single-call capacity"
        ):
            rp.prepare_candidate_triage_evidence(
                candidates,
                ["manuscript evidence"],
                minimum_chars_per_chunk=1000,
            )

    def test_budgeting_does_not_depend_on_review_thinking_allowance(self):
        candidates = [
            {
                "candidate_id": "paper:chunk-1:candidate-1",
                "source_name": "paper",
                "chunk_id": 1,
                "section": "questions raised by this chunk",
                "text": "Clarify the model.",
                "status": "candidate",
            }
        ]

        evidence, note, diagnostics = rp.prepare_candidate_triage_evidence(
            candidates,
            ["A" * 2000],
            minimum_chars_per_chunk=100,
        )

        expected = int(
            (rp.available_context() - rp.GENERATION_HEADROOM_TOKENS)
            * rp.PROMPT_CHARS_PER_TOKEN
        )
        self.assertEqual(diagnostics["capacity_chars"], expected)


class CandidateTriageTests(unittest.TestCase):

    def test_prompt_is_bounded_to_existing_candidates_and_whole_file(self):
        candidates = [
            {
                "candidate_id": "paper:chunk-1:candidate-1",
                "text": "Cluster allocation is unclear in this chunk.",
                "section": "questions raised by this chunk",
            },
            {
                "candidate_id": "paper:chunk-2:candidate-1",
                "text": (
                    "The manuscript later states that schools or classes "
                    "are randomised."
                ),
                "section": "supported points",
            },
        ]

        prompt = rp.build_candidate_triage_prompt(
            candidates,
            manuscript_text=(
                "The clusters (schools or classes) will be randomized."
            ),
            manifest_summary=(
                "Methodological features: cluster_randomised"
            ),
            method_expectations=(
                "Consider cluster definition and allocation."
            ),
        )

        self.assertIn("paper:chunk-1:candidate-1", prompt)
        self.assertIn("paper:chunk-2:candidate-1", prompt)
        self.assertIn(
            "The clusters (schools or classes) will be randomized.",
            prompt,
        )
        self.assertIn("Do not generate new", prompt)
        self.assertIn(
            "another part of the manuscript supplies that information",
            prompt,
        )
        self.assertIn("concern_candidate", prompt)
        self.assertIn("verification_candidate", prompt)

    def test_triage_is_app_owned_and_tracks_omissions(self):
        candidates = [
            {
                "candidate_id": "c1",
                "text": "Cluster sample-size justification is unclear.",
            },
            {
                "candidate_id": "c2",
                "text": "ICC assumptions are not specified.",
            },
            {
                "candidate_id": "c3",
                "text": "A chunk-local absence is resolved elsewhere.",
            },
        ]

        output = {
            "themes": [
                {
                    "theme": (
                        "Cluster design and sample-size justification"
                    ),
                    "candidate_ids": ["c1", "c2"],
                    "state": "concern_candidate",
                    "priority": "high",
                    "reason": (
                        "The related observations form one "
                        "consequential design issue."
                    ),
                }
            ]
        }

        result = rp.build_candidate_triage(candidates, output)

        self.assertEqual(
            result["assessment_type"],
            "whole_file_candidate_triage",
        )
        self.assertEqual(
            result["retained_candidate_ids"],
            ["c1", "c2"],
        )
        self.assertEqual(result["omitted_candidate_ids"], ["c3"])
        self.assertEqual(
            result["themes"][0]["state"],
            "concern_candidate",
        )
        self.assertEqual(result["themes"][0]["priority"], "high")

    def test_rejects_invented_candidate_ids(self):
        candidates = [
            {"candidate_id": "c1", "text": "Observed issue."}
        ]

        output = {
            "themes": [
                {
                    "theme": "Invented support",
                    "candidate_ids": ["c999"],
                    "state": "concern_candidate",
                    "priority": "high",
                    "reason": "Invalid invented provenance.",
                }
            ]
        }

        with self.assertRaisesRegex(
            ValueError,
            "unknown candidate IDs",
        ):
            rp.build_candidate_triage(candidates, output)

    def test_duplicate_within_theme_rejected_cross_theme_reuse_allowed(self):
        candidates = [
            {
                "candidate_id": "c1",
                "text": "One observation with two implications.",
            },
            {
                "candidate_id": "c2",
                "text": "Second observation.",
            },
        ]

        duplicate_within = {
            "themes": [
                {
                    "theme": "Bad duplicate",
                    "candidate_ids": ["c1", "c1"],
                    "state": "concern_candidate",
                    "priority": "high",
                    "reason": (
                        "Duplicate provenance should be rejected."
                    ),
                }
            ]
        }

        with self.assertRaisesRegex(
            ValueError,
            "duplicate candidate IDs",
        ):
            rp.build_candidate_triage(
                candidates,
                duplicate_within,
            )

        cross_theme = {
            "themes": [
                {
                    "theme": "Design implication",
                    "candidate_ids": ["c1"],
                    "state": "concern_candidate",
                    "priority": "high",
                    "reason": "First legitimate implication.",
                },
                {
                    "theme": "Reporting implication",
                    "candidate_ids": ["c1", "c2"],
                    "state": "verification_candidate",
                    "priority": "medium",
                    "reason": "Second distinct implication.",
                },
            ]
        }

        result = rp.build_candidate_triage(
            candidates,
            cross_theme,
        )
        self.assertEqual(len(result["themes"]), 2)
        self.assertEqual(
            result["retained_candidate_ids"],
            ["c1", "c2"],
        )

    def test_rejects_invalid_controlled_values(self):
        candidates = [
            {"candidate_id": "c1", "text": "Observed issue."}
        ]

        cases = (
            (
                "state",
                "confirmed_problem",
                "Invalid candidate triage state",
            ),
            (
                "priority",
                "critical",
                "Invalid candidate triage priority",
            ),
        )

        for field, bad_value, expected in cases:
            with self.subTest(field=field):
                theme = {
                    "theme": "Candidate theme",
                    "candidate_ids": ["c1"],
                    "state": "concern_candidate",
                    "priority": "high",
                    "reason": "Grounded reason.",
                }
                theme[field] = bad_value

                with self.assertRaisesRegex(
                    ValueError,
                    expected,
                ):
                    rp.build_candidate_triage(
                        candidates,
                        {"themes": [theme]},
                    )

    def test_uses_injected_assessor_and_schema(self):
        candidates = [
            {
                "candidate_id": "c1",
                "text": (
                    "Psychometric decision rules remain "
                    "underspecified."
                ),
                "section": (
                    "statistical / methodological concerns"
                ),
            }
        ]
        calls = []

        def assessor(*, prompt, schema):
            calls.append({
                "prompt": prompt,
                "schema": schema,
            })
            return {
                "themes": [
                    {
                        "theme": "Psychometric prespecification",
                        "candidate_ids": ["c1"],
                        "state": "concern_candidate",
                        "priority": "high",
                        "reason": (
                            "The supplied candidate remains "
                            "consequential at whole-file level."
                        ),
                    }
                ]
            }

        result = rp.triage_candidate_findings(
            candidates=candidates,
            manuscript_text=(
                "CFA will be conducted where sample size permits."
            ),
            assessor=assessor,
            manifest_summary=(
                "Methodological features: psychometric_measurement"
            ),
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0]["schema"],
            rp.candidate_triage_output_schema(),
        )
        self.assertIn("c1", calls[0]["prompt"])
        self.assertEqual(
            result["themes"][0]["theme"],
            "Psychometric prespecification",
        )
        self.assertEqual(
            result["retained_candidate_ids"],
            ["c1"],
        )
