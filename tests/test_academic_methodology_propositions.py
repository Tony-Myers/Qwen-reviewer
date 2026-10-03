"""Deterministic contract tests, not tests of a live model's semantic accuracy."""
import contextlib
import io
import unittest

import academic_chat as chat
import academic_claim_coverage as coverage
import academic_methodology as am
import reviewer_notes


class PropositionContractTests(unittest.TestCase):
    def setUp(self):
        self.claim = chat.TechnicalClaim('comparison', 'contrast',
            'Testing the contrast between groups is typically done by analyzing '
            'the interaction between group and time.', None)
        self.guidance = ('Interaction is one possible parameterisation; it is not '
                         'a universal prescription; the general principle is not '
                         '“Always test an interaction”.')
        self.passages = [reviewer_notes.Passage('test', 'test', self.guidance, 1.0)]
        text = self.claim.statement
        self.context = coverage.ClaimSourceContext(text, 0, len(text), text, 0, len(text))
        self.output = dict(claim_proposition=text, guidance_proposition=self.guidance,
            relationship='insufficient',
            reason='The guidance neither establishes typical use nor contradicts it by rejecting a universal prescription.')

    def assess(self, output, contextual=False):
        calls = []
        def judge(*, prompt, schema):
            calls.append((prompt, schema))
            return output
        if contextual:
            result = am.assess_contextual_methodological_consistency(
                claim=self.claim, source_context=self.context,
                passages=self.passages, assessor=judge)
        else:
            result = am.assess_methodological_consistency(self.claim, self.passages, judge)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], am.methodological_consistency_output_schema())
        self.assertIs(result.claim, self.claim)
        self.assertEqual(result.passages, self.passages)
        return result

    def test_schema(self):
        schema = am.methodological_consistency_output_schema()
        self.assertEqual(schema, {
            'type': 'object', 'properties': {
                'claim_proposition': {'type': 'string', 'minLength': 1},
                'guidance_proposition': {'type': 'string', 'minLength': 1},
                'relationship': {'type': 'string', 'enum': ['supports', 'incompatible', 'insufficient']},
                'reason': {'type': 'string', 'minLength': 1}},
            'required': ['claim_proposition', 'guidance_proposition', 'relationship', 'reason'],
            'additionalProperties': False})

    def test_mapping_and_public_interface(self):
        for relationship, status in [('supports', am.METHODOLOGICAL_STATUS_CONSISTENT),
                                     ('incompatible', am.METHODOLOGICAL_STATUS_CONFLICT),
                                     ('insufficient', am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED)]:
            for contextual in (False, True):
                with self.subTest(relationship=relationship, contextual=contextual):
                    result = self.assess(dict(self.output, relationship=relationship), contextual)
                    self.assertEqual(result.status, status)
                    self.assertEqual(result.assessment_error, '')
                    self.assertFalse(hasattr(result, 'claim_proposition'))
                    self.assertFalse(hasattr(result, 'relationship'))
                    if not contextual:
                        self.assertEqual(set(result.to_dict()), {'status', 'claim', 'passages', 'reasons'})

    def test_typicality_fixture_is_insufficient(self):
        # The fixture supplies the intended semantic comparison. No phrase rule
        # or live semantic accuracy is asserted by this deterministic test.
        for contextual in (False, True):
            result = self.assess(self.output, contextual)
            self.assertEqual(result.status, am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED)
            self.assertFalse(result.assessment_error)
        prompt = am.build_methodological_consistency_prompt(self.claim, self.passages)
        self.assertIn('"Typically X" and "not always/universally X" can both be true.', prompt)
        self.assertIn('Compatibility alone still does not establish supports.', prompt)

    def test_separate_significance_conflict_fixture(self):
        self.claim = chat.TechnicalClaim('comparison', 'groups',
            'Significant improvement in the intervention group and non-significant '
            'improvement in the control group establishes that the groups differ.', None)
        text = 'Separate significant/non-significant results do not establish a between-group difference.'
        self.passages = [reviewer_notes.Passage('test', 'test', text, 1.0)]
        result = self.assess(dict(claim_proposition=self.claim.statement,
            guidance_proposition=text, relationship='incompatible',
            reason='The claim asserts an inference that the guidance explicitly rejects.'))
        self.assertEqual(result.status, am.METHODOLOGICAL_STATUS_CONFLICT)
        self.assertFalse(result.assessment_error)

    def test_malformed_fields_contained_in_both_paths(self):
        invalid = [None, [], {}, dict(self.output, status='methodological_conflict'),
                   dict(self.output, extra=True), {'status': 'methodologically_consistent', 'reason': 'Legacy.'}]
        for field in self.output:
            missing = dict(self.output); del missing[field]; invalid.append(missing)
            for value in (None, [], 3, '', '   '):
                invalid.append(dict(self.output, **{field: value}))
        invalid += [dict(self.output, relationship='compatible'),
                    dict(self.output, reason=' '.join(['word'] * 31))]
        for output in invalid:
            for contextual in (False, True):
                with self.subTest(output=output, contextual=contextual):
                    with contextlib.redirect_stderr(io.StringIO()):
                        result = self.assess(output, contextual)
                    self.assertEqual(result.status, am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED)
                    self.assertIn('MethodologicalAssessmentOutputError', result.assessment_error)
                    self.assertEqual(result.reasons, [am.METHODOLOGICAL_ASSESSMENT_NOT_COMPLETED_REASON])

    def test_backend_and_programming_errors_propagate(self):
        for error in (RuntimeError('backend'), TypeError('programming')):
            def judge(**kwargs):
                raise error
            for contextual in (False, True):
                with self.subTest(error=error, contextual=contextual):
                    with self.assertRaises(type(error)):
                        if contextual:
                            am.assess_contextual_methodological_consistency(claim=self.claim,
                                source_context=self.context, passages=self.passages, assessor=judge)
                        else:
                            am.assess_methodological_consistency(self.claim, self.passages, judge)


if __name__ == '__main__':
    unittest.main()
