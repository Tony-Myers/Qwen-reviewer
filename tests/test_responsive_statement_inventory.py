import unittest

from app import review_pipeline as rp


class ResponsiveStatementInventoryTests(unittest.TestCase):

    def setUp(self):
        self.premise_id = "I1"
        self.information_need = (
            "What coefficient is reported in each relevant source statement?"
        )
        self.evidence = (
            "Source A reports coefficient 0.25. "
            "Source B reports coefficient 0.40. "
            "Source C reports coefficient 0.40."
        )

    def test_schema_requires_statement_array(self):
        schema = rp.responsive_statement_inventory_output_schema()

        self.assertEqual(schema["required"], ["statements"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["statements"]["type"],
            "array",
        )

    def test_prompt_requires_all_responsive_statements(self):
        prompt = rp.build_responsive_statement_inventory_prompt(
            self.premise_id,
            self.information_need,
            self.evidence,
        )
        normalised = " ".join(prompt.split())

        self.assertIn(
            "ALL directly responsive statements",
            normalised,
        )
        self.assertIn(
            "Do not stop after finding one plausible answer",
            normalised,
        )
        self.assertIn(
            "EXACTLY and VERBATIM",
            normalised,
        )

    def test_accepts_verbatim_source_excerpts(self):
        output = {
            "statements": [
                {"excerpt": "coefficient 0.25"},
                {"excerpt": "coefficient 0.40"},
                {"excerpt": "Source C reports coefficient 0.40"},
            ]
        }

        result = rp.build_responsive_statement_inventory(
            self.premise_id,
            self.evidence,
            output,
        )

        self.assertTrue(result["all_excerpts_source_verified"])
        self.assertEqual(len(result["statements"]), 3)
        self.assertEqual(
            result["statements"][0]["excerpt"],
            "coefficient 0.25",
        )

    def test_deduplicates_identical_verified_excerpts(self):
        output = {
            "statements": [
                {"excerpt": "coefficient 0.25"},
                {"excerpt": "coefficient 0.25"},
                {"excerpt": "coefficient 0.40"},
            ]
        }

        result = rp.build_responsive_statement_inventory(
            self.premise_id,
            self.evidence,
            output,
        )

        self.assertEqual(len(result["statements"]), 2)

    def test_rejects_paraphrased_excerpt(self):
        output = {
            "statements": [
                {
                    "excerpt": (
                        "The document says the coefficient is 0.25."
                    )
                }
            ]
        }

        with self.assertRaises(ValueError):
            rp.build_responsive_statement_inventory(
                self.premise_id,
                self.evidence,
                output,
            )

    def test_rejects_fabricated_excerpt(self):
        output = {
            "statements": [
                {"excerpt": "coefficient 0.26"}
            ]
        }

        with self.assertRaises(ValueError):
            rp.build_responsive_statement_inventory(
                self.premise_id,
                self.evidence,
                output,
            )

    def test_generation_validates_model_output(self):
        def assessor(*, prompt, schema):
            return {
                "statements": [
                    {"excerpt": "coefficient 0.25"},
                    {"excerpt": "coefficient 0.40"},
                ]
            }

        result = rp.generate_responsive_statement_inventory(
            self.premise_id,
            self.information_need,
            self.evidence,
            assessor,
        )

        self.assertEqual(
            result["assessment_type"],
            "responsive_statement_inventory",
        )
        self.assertEqual(len(result["statements"]), 2)
        self.assertTrue(result["all_excerpts_source_verified"])


if __name__ == "__main__":
    unittest.main()
