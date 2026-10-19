import unittest

from app import review_pipeline as rp


class TypedAtomProvenanceTests(unittest.TestCase):

    def test_schema_has_two_states(self):
        schema = rp.typed_atom_provenance_output_schema()
        states = schema["properties"]["provenance"]["enum"]
        self.assertEqual(
            set(states),
            {"CANDIDATE_GROUNDED", "INTRODUCED"},
        )

    def test_prompt_is_provenance_only(self):
        prompt = rp.build_typed_atom_provenance_prompt(
            "C1",
            "Timing appears concurrent.",
            "P1",
            "psychometric_timing",
            "When does psychometric work occur relative to the trial?",
        )
        self.assertIn("provenance judgement only", prompt)
        self.assertIn("Do not decide whether the candidate is true", prompt)

    def test_prompt_blocks_usefulness_substitution(self):
        prompt = rp.build_typed_atom_provenance_prompt(
            "C1",
            "Timing appears concurrent.",
            "P1",
            "final_item_set_freeze",
            "When is the item set frozen?",
        )
        self.assertIn(
            "Do not reward an atom merely because it would be useful to know",
            prompt,
        )

    def test_grounded_maps_to_true(self):
        result = rp.build_typed_atom_provenance(
            "P1",
            {
                "provenance": "CANDIDATE_GROUNDED",
                "reason": "The candidate explicitly raises timing.",
            },
        )
        self.assertTrue(result["candidate_grounded"])

    def test_introduced_maps_to_false(self):
        result = rp.build_typed_atom_provenance(
            "P1",
            {
                "provenance": "INTRODUCED",
                "reason": "The atom adds a safeguard.",
            },
        )
        self.assertFalse(result["candidate_grounded"])

    def test_unknown_state_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_typed_atom_provenance(
                "P1",
                {
                    "provenance": "DERIVED",
                    "reason": "Invalid state.",
                },
            )

    def test_unexpected_field_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_typed_atom_provenance(
                "P1",
                {
                    "provenance": "INTRODUCED",
                    "reason": "Introduced remedy.",
                    "importance": "high",
                },
            )

    def test_generation_preserves_premise_id(self):
        def assessor(*, prompt, schema):
            return {
                "provenance": "CANDIDATE_GROUNDED",
                "reason": "Explicitly raised.",
            }

        result = rp.generate_typed_atom_provenance(
            "C1",
            "No estimand is outlined.",
            "P1",
            "primary_estimand_or_time_contrast",
            "What primary estimand is specified?",
            assessor,
        )

        self.assertEqual(result["premise_id"], "P1")


if __name__ == "__main__":
    unittest.main()
