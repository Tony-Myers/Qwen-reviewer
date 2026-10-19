"""Protect live Review prompt contracts; no model classification is simulated."""
import unittest
from unittest.mock import patch
import review_pipeline as rp


class ReviewOwnershipPromptTests(unittest.TestCase):
    def capture(self, call):
        with patch.object(rp, 'apply_chat_template_compat', side_effect=lambda t, text: text), \
             patch.object(rp, 'make_default_sampler', return_value=object()), \
             patch.object(rp, 'generate', return_value='Unchanged appraisal') as generate:
            self.assertEqual(call(), 'Unchanged appraisal')
            self.assertEqual(generate.call_count, 1)
            return generate.call_args.kwargs['prompt']

    def test_shared_rules_reach_all_appraisal_stages(self):
        calls = [lambda: rp.review_chunk(None, None, rp.DocChunk('paper', 1, 'Manuscript evidence.')),
                 lambda: rp.synthesize_file_review(None, None, 'paper', 'Manuscript evidence.'),
                 lambda: rp.synthesize_report(None, None, [('paper', 'Manuscript evidence.')])]
        for call in calls:
            prompt = self.capture(call)
            with self.subTest(stage=prompt[:100]):
                # A: current misconduct/omission is not immunised by mention.
                self.assertIn('introduce or commit it, leave it unrecognised', prompt)
                self.assertIn('Acknowledgement is relevant context, not immunity from criticism.', prompt)
                self.assertIn('Preserve a concern where the evidence establishes a genuine residual problem', prompt)
                # B: issue ownership includes cited and pedagogical examples.
                self.assertIn('identify it in prior literature', prompt)
                self.assertIn('deliberately illustrate it as a pedagogical/example problem', prompt)
                self.assertIn('not by itself a concern with the current manuscript', prompt)
                # C/D: sensitivity analysis and warnings change classification context.
                self.assertIn('Do not describe a sensitivity-tested assumption as reliance on one fixed assumption', prompt)
                self.assertIn('explicitly qualified implementation setting as a silent universal recommendation', prompt)
                self.assertIn('rather than asserting a defect or suppressing the lead', prompt)
                # E: prompt vocabulary alone does not establish manuscript content.
                self.assertIn('merely because it appears in these review instructions or methodological expectations', prompt)
                self.assertIn('Include it only when the supplied manuscript evidence establishes that it is present.', prompt)

    def test_final_synthesis_classification_and_headings(self):
        prompt = self.capture(lambda: rp.synthesize_report(None, None, [('paper', 'Evidence.')]))
        self.assertIn('First determine whether a residual manuscript concern remains', prompt)
        self.assertIn('If none remains, do not present the issue under "Directly supported concerns"', prompt)
        self.assertIn('describe the manuscript\'s treatment in the same bullet', prompt)
        self.assertIn('strength, neutral observation, evidence-motivated verification prompt, or omit it', prompt)
        for heading in ('Overall synopsis', 'Major strengths', 'Directly supported concerns',
                        'Verification prompts', 'Extraction limits', 'Overall confidence'):
            self.assertIn('# ' + heading, prompt)

    def test_validator_reclassifies_without_suppressing_residual_issues(self):
        prompt = self.capture(lambda: rp.validate_report_against_evidence(
            None, None, 'Appraisal.', [('paper', 'Evidence.')]))
        for term in ('author-recognised issue', 'sensitivity or robustness analysis',
                     'explicit methodological warning or implementation instruction',
                     'pedagogical demonstration', 'problem in cited/prior research'):
            self.assertIn(term, prompt)
        self.assertIn('Reclassify or remove a concern when the supplied evidence shows', prompt)
        self.assertIn('Preserve a concern where the evidence establishes one', prompt)
        self.assertIn('the residual problem and the manuscript\'s treatment in the same bullet', prompt)
        self.assertIn('do not suppress worthwhile investigative leads', prompt)
        self.assertIn('Remove a method, analysis, diagnostic, framework, limitation or feature from the synopsis', prompt)
        self.assertIn('if it appears only in review instructions or methodological expectations', prompt)
        self.assertIn('Do not introduce new criticisms.', prompt)


if __name__ == '__main__':
    unittest.main()
