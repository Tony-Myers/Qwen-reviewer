import unittest

from app import review_pipeline as rp


class SourcePremiseResolutionTests(unittest.TestCase):

    def test_schema_is_strict(self):
        schema = rp.source_premise_resolution_output_schema()
        self.assertEqual(schema["required"], ["resolution"])
        self.assertFalse(schema["additionalProperties"])
        resolution = schema["properties"]["resolution"]
        self.assertFalse(resolution["additionalProperties"])

    def test_prompt_is_neutral_source_resolution(self):
        prompt = rp.build_source_premise_resolution_prompt(
            "P1",
            "What does the manuscript specify?",
            "The manuscript specifies X.",
        )
        self.assertIn("source resolution, not peer review", prompt)
        self.assertIn("do not decide whether", prompt)
        normalised_prompt = " ".join(prompt.split())
        self.assertIn(
            "does NOT mean the manuscript omits",
            normalised_prompt,
        )
        self.assertNotIn("methodological concern", prompt.lower())

    def test_answered_resolution_is_valid(self):
        result = rp.build_source_premise_resolution(
            "P1",
            {
                "resolution": {
                    "premise_id": "P1",
                    "status": "ANSWERED",
                    "source_answer": "The manuscript specifies X.",
                    "residual_question": "",
                }
            },
        )
        self.assertEqual(
            result["resolution"]["status"],
            "ANSWERED",
        )

    def test_partial_requires_residual(self):
        with self.assertRaises(ValueError):
            rp.build_source_premise_resolution(
                "P1",
                {
                    "resolution": {
                        "premise_id": "P1",
                        "status": "PARTIAL",
                        "source_answer": "Partly specified.",
                        "residual_question": "",
                    }
                },
            )

    def test_wrong_premise_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            rp.build_source_premise_resolution(
                "P1",
                {
                    "resolution": {
                        "premise_id": "P2",
                        "status": "ANSWERED",
                        "source_answer": "Specified.",
                        "residual_question": "",
                    }
                },
            )

    def test_not_located_has_no_residual(self):
        result = rp.build_source_premise_resolution(
            "P1",
            {
                "resolution": {
                    "premise_id": "P1",
                    "status": "NOT_LOCATED",
                    "source_answer": "",
                    "residual_question": "",
                }
            },
        )
        self.assertEqual(
            result["resolution"]["status"],
            "NOT_LOCATED",
        )

    def test_generation_uses_assessor(self):
        seen = {}

        def assessor(*, prompt, schema):
            seen["prompt"] = prompt
            seen["schema"] = schema
            return {
                "resolution": {
                    "premise_id": "P1",
                    "status": "ANSWERED",
                    "source_answer": "The manuscript specifies X.",
                    "residual_question": "",
                }
            }

        result = rp.generate_source_premise_resolution(
            "P1",
            "What does the manuscript specify?",
            "The manuscript specifies X.",
            assessor,
        )

        self.assertIn("SOURCE QUESTION", seen["prompt"])
        self.assertIn("resolution", seen["schema"]["properties"])
        self.assertEqual(
            result["resolution"]["premise_id"],
            "P1",
        )


if __name__ == "__main__":
    unittest.main()
