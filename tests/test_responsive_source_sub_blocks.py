import unittest

from app import review_pipeline as rp


class ResponsiveSourceSubBlockTests(unittest.TestCase):

    def block(self, block_id="paper:segment-1:sub-block-1", text="Evidence"):
        return {
            "block_id": block_id,
            "parent_segment_id": "paper:segment-1",
            "source_name": "paper",
            "block_index": 1,
            "parent_start_char": 0,
            "parent_end_char": len(text),
            "source_start_char": 0,
            "source_end_char": len(text),
            "text": text,
        }

    def test_schema_has_two_states(self):
        schema = rp.responsive_source_sub_block_output_schema()
        states = set(schema["properties"]["state"]["enum"])
        self.assertEqual(states, {"RESPONSIVE", "NOT_RESPONSIVE"})

    def test_prompt_is_high_recall_and_specific(self):
        prompt = rp.build_responsive_source_sub_block_prompt(
            "P1",
            "What unit is randomised?",
            self.block(text="Schools were randomised."),
        )
        self.assertIn("partial answer counts as RESPONSIVE", prompt)
        self.assertIn("potentially conflicting answer counts as RESPONSIVE", prompt)
        self.assertIn("Shared terminology alone is not enough", prompt)
        self.assertIn("different analysis", prompt)
        self.assertIn("Do not resolve conflicts", prompt)
        self.assertIn("Do not quote, rewrite, or extract", prompt)

    def test_build_responsive(self):
        block = self.block()
        result = rp.build_responsive_source_sub_block_assessment(
            "P1",
            block,
            {"state": "RESPONSIVE", "reason": "Directly states the unit."},
        )
        self.assertEqual(result["state"], "RESPONSIVE")
        self.assertEqual(result["block_id"], block["block_id"])

    def test_build_not_responsive(self):
        result = rp.build_responsive_source_sub_block_assessment(
            "P1",
            self.block(),
            {"state": "NOT_RESPONSIVE", "reason": "Different analysis."},
        )
        self.assertEqual(result["state"], "NOT_RESPONSIVE")

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            rp.build_responsive_source_sub_block_assessment(
                "P1",
                self.block(),
                {
                    "state": "RESPONSIVE",
                    "reason": "Relevant.",
                    "answer": "invented",
                },
            )

    def test_generation_uses_contract(self):
        block = self.block(text="Schools were randomised.")

        def assessor(*, prompt, schema):
            self.assertIn("Schools were randomised.", prompt)
            self.assertIn("state", schema["properties"])
            return {
                "state": "RESPONSIVE",
                "reason": "Directly states the randomisation unit.",
            }

        result = rp.generate_responsive_source_sub_block_assessment(
            "P1",
            "What unit is randomised?",
            block,
            assessor,
        )
        self.assertEqual(result["state"], "RESPONSIVE")

    def test_summary_complete_and_no_absence_authority(self):
        b1 = self.block("paper:segment-1:sub-block-1", "A")
        b2 = self.block("paper:segment-1:sub-block-2", "B")
        assessments = [
            {
                "assessment_type": "responsive_source_sub_block",
                "premise_id": "P1",
                "block_id": b1["block_id"],
                "state": "RESPONSIVE",
                "reason": "Relevant.",
            },
            {
                "assessment_type": "responsive_source_sub_block",
                "premise_id": "P1",
                "block_id": b2["block_id"],
                "state": "NOT_RESPONSIVE",
                "reason": "Different analysis.",
            },
        ]

        summary = rp.summarise_responsive_source_sub_blocks(
            "P1", [b1, b2], assessments
        )

        self.assertTrue(summary["screen_complete"])
        self.assertEqual(summary["responsive_block_ids"], [b1["block_id"]])
        self.assertFalse(summary["negative_coverage_claim_authorised"])

    def test_summary_records_incomplete_screen(self):
        b1 = self.block("paper:segment-1:sub-block-1", "A")
        b2 = self.block("paper:segment-1:sub-block-2", "B")

        assessment = {
            "assessment_type": "responsive_source_sub_block",
            "premise_id": "P1",
            "block_id": b1["block_id"],
            "state": "RESPONSIVE",
            "reason": "Relevant.",
        }

        summary = rp.summarise_responsive_source_sub_blocks(
            "P1", [b1, b2], [assessment]
        )

        self.assertFalse(summary["screen_complete"])
        self.assertEqual(
            summary["unscreened_block_ids"],
            [b2["block_id"]],
        )


if __name__ == "__main__":
    unittest.main()
