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
        self.claim = chat.TechnicalClaim(
            'comparison',
            'contrast',
            'Testing the contrast between groups is typically done by analyzing '
            'the interaction between group and time.',
            None,
        )
        self.guidance = (
            'Interaction is one possible parameterisation; it is not a '
            'universal prescription; the general principle is not '
            '“Always test an interaction”.'
        )
        self.passages = [
            reviewer_notes.Passage('test', 'test', self.guidance, 1.0)
        ]
        text = self.claim.statement
        self.context = coverage.ClaimSourceContext(
            text, 0, len(text), text, 0, len(text)
        )

    def coexistence_output(self, value='yes', reason='The propositions can coexist.'):
        return {
            'claim_proposition': self.claim.statement,
            'guidance_proposition': self.guidance,
            'can_both_be_true': value,
            'reason': reason,
        }

    def establishment_output(
        self,
        value='no',
        reason='The guidance does not establish the complete claim.',
    ):
        return {
            'claim_proposition': self.claim.statement,
            'guidance_proposition': self.guidance,
            'guidance_establishes_claim': value,
            'reason': reason,
        }

    def assess(
        self,
        coexistence=None,
        establishment=None,
        contextual=False,
    ):
        coexistence = (
            self.coexistence_output()
            if coexistence is None
            else coexistence
        )
        establishment = (
            self.establishment_output()
            if establishment is None
            else establishment
        )

        calls = []

        def judge(*, prompt, schema):
            calls.append((prompt, schema))
            if schema == am.methodological_coexistence_output_schema():
                return coexistence
            if schema == am.methodological_establishment_output_schema():
                return establishment
            raise AssertionError('Unexpected methodology schema.')

        if contextual:
            result = am.assess_contextual_methodological_consistency(
                claim=self.claim,
                source_context=self.context,
                passages=self.passages,
                assessor=judge,
            )
        else:
            result = am.assess_methodological_consistency(
                self.claim,
                self.passages,
                judge,
            )

        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0][1],
            am.methodological_coexistence_output_schema(),
        )
        self.assertEqual(
            calls[1][1],
            am.methodological_establishment_output_schema(),
        )
        self.assertIs(result.claim, self.claim)
        self.assertEqual(result.passages, self.passages)
        return result, calls

    def test_schemas_are_separate_and_strict(self):
        self.assertEqual(
            am.methodological_coexistence_output_schema(),
            {
                'type': 'object',
                'properties': {
                    'claim_proposition': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'guidance_proposition': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'can_both_be_true': {
                        'type': 'string',
                        'enum': ['yes', 'no', 'unclear'],
                    },
                    'reason': {
                        'type': 'string',
                        'minLength': 1,
                    },
                },
                'required': [
                    'claim_proposition',
                    'guidance_proposition',
                    'can_both_be_true',
                    'reason',
                ],
                'additionalProperties': False,
            },
        )
        self.assertEqual(
            am.methodological_establishment_output_schema(),
            {
                'type': 'object',
                'properties': {
                    'claim_proposition': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'guidance_proposition': {
                        'type': 'string',
                        'minLength': 1,
                    },
                    'guidance_establishes_claim': {
                        'type': 'string',
                        'enum': ['yes', 'no', 'unclear'],
                    },
                    'reason': {
                        'type': 'string',
                        'minLength': 1,
                    },
                },
                'required': [
                    'claim_proposition',
                    'guidance_proposition',
                    'guidance_establishes_claim',
                    'reason',
                ],
                'additionalProperties': False,
            },
        )

    def test_application_derives_status_from_bounded_judgements(self):
        cases = [
            (
                'yes',
                'yes',
                am.METHODOLOGICAL_STATUS_CONSISTENT,
            ),
            (
                'yes',
                'no',
                am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            ),
            (
                'yes',
                'unclear',
                am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            ),
            (
                'unclear',
                'yes',
                am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            ),
            (
                'unclear',
                'no',
                am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            ),
            (
                'unclear',
                'unclear',
                am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
            ),
            (
                'no',
                'yes',
                am.METHODOLOGICAL_STATUS_CONFLICT,
            ),
            (
                'no',
                'no',
                am.METHODOLOGICAL_STATUS_CONFLICT,
            ),
            (
                'no',
                'unclear',
                am.METHODOLOGICAL_STATUS_CONFLICT,
            ),
        ]

        for coexistence, establishment, expected in cases:
            for contextual in (False, True):
                with self.subTest(
                    coexistence=coexistence,
                    establishment=establishment,
                    contextual=contextual,
                ):
                    result, _ = self.assess(
                        coexistence=self.coexistence_output(coexistence),
                        establishment=self.establishment_output(establishment),
                        contextual=contextual,
                    )
                    self.assertEqual(result.status, expected)
                    self.assertEqual(result.assessment_error, '')
                    self.assertFalse(
                        hasattr(result, 'can_both_be_true')
                    )
                    self.assertFalse(
                        hasattr(result, 'guidance_establishes_claim')
                    )
                    if not contextual:
                        self.assertEqual(
                            set(result.to_dict()),
                            {'status', 'claim', 'passages', 'reasons'},
                        )

    def test_successful_result_preserves_both_bounded_reasons(self):
        coexistence_reason = (
            'Typical usage can coexist with a non-universal prescription.'
        )
        establishment_reason = (
            'The guidance does not establish the asserted typical frequency.'
        )
        result, _ = self.assess(
            coexistence=self.coexistence_output(
                'yes',
                coexistence_reason,
            ),
            establishment=self.establishment_output(
                'no',
                establishment_reason,
            ),
        )
        self.assertEqual(
            result.reasons,
            [coexistence_reason, establishment_reason],
        )

    def test_prompts_keep_semantic_tasks_separate(self):
        coexistence = am.build_methodological_coexistence_prompt(
            self.claim,
            self.passages,
        )
        establishment = am.build_methodological_establishment_prompt(
            self.claim,
            self.passages,
        )

        self.assertIn(
            'Can both material propositions be true',
            coexistence,
        )
        self.assertIn(
            'Do not decide whether the guidance supports the claim.',
            coexistence,
        )
        self.assertNotIn(
            'guidance_establishes_claim',
            coexistence,
        )

        self.assertIn(
            "Does the supplied guidance establish the claim's complete "
            'material',
            establishment,
        )
        self.assertIn(
            'Do not decide whether the propositions conflict.',
            establishment,
        )
        self.assertNotIn(
            'can_both_be_true',
            establishment,
        )

    def test_modal_counterexample_rule_is_general(self):
        prompt = am.build_methodological_coexistence_prompt(
            self.claim,
            self.passages,
        )
        self.assertIn(
            'A universal or necessary proposition cannot',
            prompt,
        )
        self.assertIn(
            'permitted counterexample under the',
            prompt,
        )
        self.assertIn(
            '"Typically X" and "not always/universally X" can both be true.',
            prompt,
        )

    def test_contextual_prompts_preserve_context_authority_boundary(self):
        coexistence = (
            am.build_contextual_methodological_coexistence_prompt(
                claim=self.claim,
                source_context=self.context,
                passages=self.passages,
            )
        )
        establishment = (
            am.build_contextual_methodological_establishment_prompt(
                claim=self.claim,
                source_context=self.context,
                passages=self.passages,
            )
        )

        for prompt in (coexistence, establishment):
            self.assertIn('VERIFIED SOURCE SENTENCE', prompt)
            self.assertIn('BOUNDED ANSWER CONTEXT', prompt)
            self.assertIn(
                'The answer context is not methodological guidance',
                prompt,
            )
            self.assertIn(
                'Only the supplied curated methodological guidance may '
                'establish',
                prompt,
            )
            self.assertIn(
                'Do not rewrite, repair, strengthen, or weaken the '
                'generated claim.',
                prompt,
            )

    def test_separate_significance_conflict_fixture(self):
        self.claim = chat.TechnicalClaim(
            'comparison',
            'groups',
            'Significant improvement in the intervention group and '
            'non-significant improvement in the control group establishes '
            'that the groups differ.',
            None,
        )
        text = (
            'Separate significant/non-significant results do not establish '
            'a between-group difference.'
        )
        self.guidance = text
        self.passages = [
            reviewer_notes.Passage('test', 'test', text, 1.0)
        ]

        result, _ = self.assess(
            coexistence=self.coexistence_output(
                'no',
                'The claim asserts an inference that the guidance rejects.',
            ),
            establishment=self.establishment_output(
                'no',
                'The guidance does not establish the claimed inference.',
            ),
        )
        self.assertEqual(
            result.status,
            am.METHODOLOGICAL_STATUS_CONFLICT,
        )
        self.assertFalse(result.assessment_error)

    def test_malformed_coexistence_output_is_contained(self):
        valid = self.coexistence_output()
        invalid = [
            None,
            [],
            {},
            dict(valid, extra=True),
            {
                'status': 'methodological_conflict',
                'reason': 'Legacy.',
            },
        ]

        for field in valid:
            missing = dict(valid)
            del missing[field]
            invalid.append(missing)
            for value in (None, [], 3, '', '   '):
                invalid.append(dict(valid, **{field: value}))

        invalid += [
            dict(valid, can_both_be_true='compatible'),
            dict(valid, reason=' '.join(['word'] * 31)),
        ]

        for output in invalid:
            for contextual in (False, True):
                with self.subTest(
                    output=output,
                    contextual=contextual,
                ):
                    calls = []

                    def judge(*, prompt, schema):
                        calls.append(schema)
                        if (
                            schema
                            == am.methodological_coexistence_output_schema()
                        ):
                            return output
                        raise AssertionError(
                            'Establishment call should not occur after '
                            'unusable coexistence output.'
                        )

                    with contextlib.redirect_stderr(io.StringIO()):
                        if contextual:
                            result = (
                                am.assess_contextual_methodological_consistency(
                                    claim=self.claim,
                                    source_context=self.context,
                                    passages=self.passages,
                                    assessor=judge,
                                )
                            )
                        else:
                            result = am.assess_methodological_consistency(
                                self.claim,
                                self.passages,
                                judge,
                            )

                    self.assertEqual(len(calls), 1)
                    self.assertEqual(
                        result.status,
                        am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
                    )
                    self.assertIn(
                        'MethodologicalAssessmentOutputError',
                        result.assessment_error,
                    )
                    self.assertEqual(
                        result.reasons,
                        [
                            am.METHODOLOGICAL_ASSESSMENT_NOT_COMPLETED_REASON
                        ],
                    )

    def test_malformed_establishment_output_is_contained(self):
        valid = self.establishment_output()
        invalid = [
            None,
            [],
            {},
            dict(valid, extra=True),
        ]

        for field in valid:
            missing = dict(valid)
            del missing[field]
            invalid.append(missing)
            for value in (None, [], 3, '', '   '):
                invalid.append(dict(valid, **{field: value}))

        invalid += [
            dict(valid, guidance_establishes_claim='supports'),
            dict(valid, reason=' '.join(['word'] * 31)),
        ]

        for output in invalid:
            for contextual in (False, True):
                with self.subTest(
                    output=output,
                    contextual=contextual,
                ):
                    calls = []

                    def judge(*, prompt, schema):
                        calls.append(schema)
                        if (
                            schema
                            == am.methodological_coexistence_output_schema()
                        ):
                            return self.coexistence_output()
                        if (
                            schema
                            == am.methodological_establishment_output_schema()
                        ):
                            return output
                        raise AssertionError('Unexpected schema.')

                    with contextlib.redirect_stderr(io.StringIO()):
                        if contextual:
                            result = (
                                am.assess_contextual_methodological_consistency(
                                    claim=self.claim,
                                    source_context=self.context,
                                    passages=self.passages,
                                    assessor=judge,
                                )
                            )
                        else:
                            result = am.assess_methodological_consistency(
                                self.claim,
                                self.passages,
                                judge,
                            )

                    self.assertEqual(len(calls), 2)
                    self.assertEqual(
                        result.status,
                        am.METHODOLOGICAL_STATUS_NOT_ESTABLISHED,
                    )
                    self.assertIn(
                        'MethodologicalAssessmentOutputError',
                        result.assessment_error,
                    )

    def test_backend_and_programming_errors_propagate(self):
        for error in (
            RuntimeError('backend'),
            TypeError('programming'),
        ):
            def judge(**kwargs):
                raise error

            for contextual in (False, True):
                with self.subTest(
                    error=error,
                    contextual=contextual,
                ):
                    with self.assertRaises(type(error)):
                        if contextual:
                            am.assess_contextual_methodological_consistency(
                                claim=self.claim,
                                source_context=self.context,
                                passages=self.passages,
                                assessor=judge,
                            )
                        else:
                            am.assess_methodological_consistency(
                                self.claim,
                                self.passages,
                                judge,
                            )


if __name__ == '__main__':
    unittest.main()
