import unittest

from app import review_pipeline as rp


class CandidateAtomicQuestionTests(unittest.TestCase):

    def test_schema_is_strict(self):
        schema = rp.candidate_atomic_questions_output_schema()
        self.assertEqual(schema["required"], ["questions"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["questions"]["maxItems"],
            8,
        )

    def test_prompt_separates_premise_from_remedy(self):
        prompt = rp.build_candidate_atomic_questions_prompt(
            "C1",
            "The measure may change; verify whether it is frozen.",
        )
        normalised = " ".join(prompt.split())
        self.assertIn(
            "factual premise underlying a criticism from a remedy",
            normalised,
        )
        self.assertIn(
            "do not automatically turn the proposed remedy into another question",
            normalised,
        )

    def test_prompt_protects_longitudinal_information_need(self):
        prompt = rp.build_candidate_atomic_questions_prompt(
            "C1",
            "The repeated outcome analysis is unclear.",
        )
        normalised = " ".join(prompt.split())
        self.assertIn(
            "primary estimand/time contrast",
            normalised,
        )
        self.assertIn(
            "representation of repeated observations",
            normalised,
        )

    def test_builder_assigns_app_owned_premise_ids(self):
        result = rp.build_candidate_atomic_questions(
            "C1",
            {
                "questions": [
                    {"question": "What is the primary outcome?"},
                    {"question": "What model is specified?"},
                ]
            },
        )
        self.assertEqual(
            [q["premise_id"] for q in result["questions"]],
            ["C1:premise-1", "C1:premise-2"],
        )

    def test_duplicate_questions_are_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_candidate_atomic_questions(
                "C1",
                {
                    "questions": [
                        {"question": "What model is specified?"},
                        {"question": "  what MODEL is specified?  "},
                    ]
                },
            )

    def test_unexpected_question_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_candidate_atomic_questions(
                "C1",
                {
                    "questions": [
                        {
                            "question": "What model is specified?",
                            "criticism": "No model.",
                        }
                    ]
                },
            )

    def test_generation_uses_assessor(self):
        seen = {}

        def assessor(*, prompt, schema):
            seen["prompt"] = prompt
            seen["schema"] = schema
            return {
                "questions": [
                    {"question": "What model is specified?"}
                ]
            }

        result = rp.generate_candidate_atomic_questions(
            "C1",
            "No model is specified in this chunk.",
            assessor,
        )

        self.assertIn("PRELIMINARY CANDIDATE", seen["prompt"])
        self.assertIn("questions", seen["schema"]["properties"])
        self.assertEqual(result["candidate_id"], "C1")
        self.assertEqual(len(result["questions"]), 1)


if __name__ == "__main__":
    unittest.main()
