import unittest

from app import review_pipeline as rp


class TypedSourceResolutionTests(unittest.TestCase):

    def test_prompt_preserves_information_need(self):
        prompt = rp.build_typed_source_resolution_prompt(
            "P1",
            "primary_estimand_or_time_contrast",
            "What is the primary estimand?",
            "The primary outcome is Y.",
        )
        self.assertIn(
            "INFORMATION NEED:\nprimary_estimand_or_time_contrast",
            prompt,
        )
        self.assertIn(
            "An outcome variable is not itself an estimand",
            prompt,
        )

    def test_prompt_preserves_within_participant_target(self):
        prompt = rp.build_typed_source_resolution_prompt(
            "P1",
            "within_participant_repeated_structure",
            "How are repeated observations represented?",
            "The model has a random intercept for cluster.",
        )
        self.assertIn(
            "dependency among repeated observations from the same participant",
            prompt,
        )
        self.assertIn(
            "higher-level cluster does not by itself specify",
            prompt,
        )

    def test_unknown_information_need_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_typed_source_resolution_prompt(
                "P1",
                "unknown_target",
                "What is specified?",
                "Some evidence.",
            )

    def test_generation_uses_existing_resolution_contract(self):
        def assessor(*, prompt, schema):
            return {
                "resolution": {
                    "premise_id": "P1",
                    "status": "NOT_LOCATED",
                    "source_answer": "",
                    "residual_question": "",
                }
            }

        result = rp.generate_typed_source_resolution(
            "P1",
            "primary_estimand_or_time_contrast",
            "What is the primary estimand?",
            "The primary outcome is Y.",
            assessor,
        )

        self.assertEqual(
            result["assessment_type"],
            "source_premise_resolution",
        )
        self.assertEqual(
            result["resolution"]["status"],
            "NOT_LOCATED",
        )

    def test_wrong_premise_id_rejected(self):
        def assessor(*, prompt, schema):
            return {
                "resolution": {
                    "premise_id": "WRONG",
                    "status": "NOT_LOCATED",
                    "source_answer": "",
                    "residual_question": "",
                }
            }

        with self.assertRaises(ValueError):
            rp.generate_typed_source_resolution(
                "P1",
                "factorial_analysis_model",
                "What model is specified?",
                "A Bayesian model is specified.",
                assessor,
            )


if __name__ == "__main__":
    unittest.main()
