import unittest

from app import review_pipeline as rp


class MethodologicalAppraisalTests(unittest.TestCase):

    def test_schema_exposes_four_states(self):
        schema = rp.methodological_appraisal_output_schema()
        states = set(
            schema["properties"]["appraisal"]
            ["properties"]["state"]["enum"]
        )
        self.assertEqual(
            states,
            {
                "CONCERN_SUPPORTED",
                "NO_CONCERN",
                "NEEDS_MORE_SOURCE_EVIDENCE",
                "NEEDS_MORE_METHODOLOGICAL_CONTEXT",
            },
        )

    def test_resolved_state_requires_empty_dependency(self):
        result = rp.build_methodological_appraisal({
            "appraisal": {
                "state": "NO_CONCERN",
                "reason": "The source resolves the premise.",
                "residual_dependency": "",
            }
        })
        self.assertEqual(result["state"], "NO_CONCERN")

    def test_resolved_state_rejects_dependency(self):
        with self.assertRaises(ValueError):
            rp.build_methodological_appraisal({
                "appraisal": {
                    "state": "CONCERN_SUPPORTED",
                    "reason": "Concern established.",
                    "residual_dependency": "Need something else.",
                }
            })

    def test_needs_more_requires_dependency(self):
        with self.assertRaises(ValueError):
            rp.build_methodological_appraisal({
                "appraisal": {
                    "state": "NEEDS_MORE_SOURCE_EVIDENCE",
                    "reason": "Evidence is incomplete.",
                    "residual_dependency": "",
                }
            })

    def test_needs_more_context_accepts_dependency(self):
        result = rp.build_methodological_appraisal({
            "appraisal": {
                "state": "NEEDS_MORE_METHODOLOGICAL_CONTEXT",
                "reason": "The source facts are established.",
                "residual_dependency": (
                    "The inferential claim the comparison is intended "
                    "to support."
                ),
            }
        })
        self.assertEqual(
            result["state"],
            "NEEDS_MORE_METHODOLOGICAL_CONTEXT",
        )

    def test_prompt_marks_remedy_as_non_authoritative(self):
        prompt = rp.build_methodological_appraisal_prompt(
            "Candidate.",
            [
                {
                    "role": "REMEDY_OR_REQUIREMENT",
                    "text": "Use method X.",
                }
            ],
            [
                {
                    "premise_id": "P1",
                    "status": "NOT_LOCATED",
                    "source_answer": "",
                    "residual_question": "",
                }
            ],
            "MANUSCRIPT_UNRESOLVED",
        )
        self.assertIn(
            "A REMEDY_OR_REQUIREMENT is a reviewer proposal",
            prompt,
        )
        self.assertIn(
            "NOT_LOCATED does not mean",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
