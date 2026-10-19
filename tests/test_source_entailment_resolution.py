import unittest

from app import review_pipeline as rp


class SourceEntailmentResolutionTests(unittest.TestCase):

    def test_prompt_requires_specific_answer(self):
        prompt = rp.build_strict_source_entailment_prompt(
            "E1",
            "What is the primary estimand?",
            "The primary outcome is measured at four time points.",
        )
        normalised = " ".join(prompt.split())
        self.assertIn(
            "ANSWERED requires an answer to the SPECIFIC question asked",
            normalised,
        )
        self.assertIn(
            "merely related to the question is not enough",
            normalised,
        )

    def test_prompt_does_not_infer_estimand_from_time_points(self):
        prompt = rp.build_strict_source_entailment_prompt(
            "E1",
            "What is the primary time contrast?",
            "Measurements occur at baseline and follow-up.",
        )
        normalised = " ".join(prompt.split())
        self.assertIn(
            "does not by itself identify which post-baseline time point",
            normalised,
        )

    def test_prompt_separates_cluster_and_repeated_dependency(self):
        prompt = rp.build_strict_source_entailment_prompt(
            "E1",
            "How are repeated observations represented?",
            "The model has a random intercept for cluster.",
        )
        normalised = " ".join(prompt.split())
        self.assertIn(
            "random intercept for cluster describes between-cluster dependency",
            normalised,
        )
        self.assertIn(
            "does not by itself specify the representation of repeated observations",
            normalised,
        )

    def test_generation_reuses_source_resolution_contract(self):
        def assessor(*, prompt, schema):
            return {
                "resolution": {
                    "premise_id": "E1",
                    "status": "NOT_LOCATED",
                    "source_answer": "",
                    "residual_question": "",
                }
            }

        result = rp.generate_strict_source_entailment_resolution(
            "E1",
            "What is the primary estimand?",
            "The primary outcome is measured at four time points.",
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

    def test_generation_rejects_wrong_premise_id(self):
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
            rp.generate_strict_source_entailment_resolution(
                "E1",
                "What is the primary estimand?",
                "No estimand is stated in this evidence.",
                assessor,
            )


if __name__ == "__main__":
    unittest.main()
