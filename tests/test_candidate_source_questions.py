import unittest

from app import review_pipeline as rp


class CandidateSourceQuestionTests(unittest.TestCase):

    def test_schema_is_strict(self):
        schema = rp.candidate_source_question_output_schema()
        self.assertEqual(schema["required"], ["source_question"])
        self.assertFalse(schema["additionalProperties"])

    def test_prompt_explicitly_neutralises_chunk_absence(self):
        prompt = rp.build_candidate_source_question_prompt(
            "C1",
            "The randomisation unit is not specified in this chunk.",
        )
        normalised = " ".join(prompt.split())
        self.assertIn(
            "absence in the candidate's local chunk is an absence "
            "from the whole manuscript",
            normalised,
        )

    def test_prompt_does_not_ask_model_to_answer_source_question(self):
        prompt = rp.build_candidate_source_question_prompt(
            "C1",
            "The model is unclear.",
        )
        self.assertIn("Do not answer the question.", prompt)

    def test_valid_question_preserves_candidate_id(self):
        result = rp.build_candidate_source_question(
            "C1",
            {"source_question": "What model does the manuscript specify?"},
        )
        self.assertEqual(result["candidate_id"], "C1")
        self.assertEqual(
            result["source_question"],
            "What model does the manuscript specify?",
        )

    def test_empty_question_is_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_candidate_source_question(
                "C1",
                {"source_question": "   "},
            )

    def test_unexpected_output_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_candidate_source_question(
                "C1",
                {
                    "source_question": "What is specified?",
                    "criticism": "Something is missing.",
                },
            )

    def test_generation_uses_assessor(self):
        seen = {}

        def assessor(*, prompt, schema):
            seen["prompt"] = prompt
            seen["schema"] = schema
            return {
                "source_question": (
                    "What does the manuscript specify as the "
                    "randomisation unit?"
                )
            }

        result = rp.generate_candidate_source_question(
            "C1",
            "The randomisation unit is unclear.",
            assessor,
        )

        self.assertIn("PRELIMINARY CANDIDATE", seen["prompt"])
        self.assertIn(
            "source_question",
            seen["schema"]["properties"],
        )
        self.assertEqual(result["candidate_id"], "C1")


if __name__ == "__main__":
    unittest.main()
