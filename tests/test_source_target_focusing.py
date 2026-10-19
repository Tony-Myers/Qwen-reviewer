import unittest

from app import review_pipeline as rp


class SourceTargetFocusingTests(unittest.TestCase):

    def setUp(self):
        self.segment = {
            "segment_id": "paper.pdf:source-segment-1",
            "source_name": "paper.pdf",
            "segment_index": 1,
            "start_char": 0,
            "end_char": 20,
            "text": "responsive evidence",
        }

    def test_schema_has_two_states_and_bounded_reason(self):
        schema = rp.source_target_focusing_output_schema()
        self.assertEqual(
            set(schema["properties"]["state"]["enum"]),
            {"ANSWER_CAPABLE", "CONTEXT_ONLY"},
        )
        self.assertEqual(
            schema["properties"]["reason"]["minLength"],
            1,
        )
        self.assertEqual(
            schema["properties"]["reason"]["maxLength"],
            700,
        )

    def test_prompt_preserves_exact_segment(self):
        prompt = rp.build_source_target_focusing_prompt(
            "candidate:semantic-1",
            "requested implementation detail",
            self.segment,
        )
        self.assertIn("responsive evidence", prompt)
        self.assertIn("requested implementation detail", prompt)
        self.assertIn("ANSWER_CAPABLE", prompt)
        self.assertIn("CONTEXT_ONLY", prompt)
        self.assertIn(
            "Do not decide that information is absent from the manuscript",
            prompt,
        )

    def test_build_answer_capable(self):
        result = rp.build_source_target_focusing(
            "candidate:semantic-1",
            self.segment,
            {
                "state": "ANSWER_CAPABLE",
                "reason": "Contains the requested specification.",
            },
        )
        self.assertEqual(result["state"], "ANSWER_CAPABLE")
        self.assertEqual(
            result["segment_id"],
            "paper.pdf:source-segment-1",
        )

    def test_build_context_only(self):
        result = rp.build_source_target_focusing(
            "candidate:semantic-1",
            self.segment,
            {
                "state": "CONTEXT_ONLY",
                "reason": "Mentions the model but not the requested detail.",
            },
        )
        self.assertEqual(result["state"], "CONTEXT_ONLY")

    def test_rejects_unknown_state(self):
        with self.assertRaises(ValueError):
            rp.build_source_target_focusing(
                "candidate:semantic-1",
                self.segment,
                {
                    "state": "NOT_IN_MANUSCRIPT",
                    "reason": "Invalid absence judgement.",
                },
            )

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            rp.build_source_target_focusing(
                "candidate:semantic-1",
                self.segment,
                {
                    "state": "ANSWER_CAPABLE",
                    "reason": "Responsive.",
                    "absence": True,
                },
            )

    def test_rejects_long_reason(self):
        with self.assertRaises(ValueError):
            rp.build_source_target_focusing(
                "candidate:semantic-1",
                self.segment,
                {
                    "state": "ANSWER_CAPABLE",
                    "reason": "x" * 701,
                },
            )

    def test_summary_complete(self):
        segment2 = dict(self.segment)
        segment2.update({
            "segment_id": "paper.pdf:source-segment-2",
            "segment_index": 2,
            "start_char": 20,
            "end_char": 40,
            "text": "context",
        })

        records = [
            rp.build_source_target_focusing(
                "candidate:semantic-1",
                self.segment,
                {
                    "state": "ANSWER_CAPABLE",
                    "reason": "Responsive.",
                },
            ),
            rp.build_source_target_focusing(
                "candidate:semantic-1",
                segment2,
                {
                    "state": "CONTEXT_ONLY",
                    "reason": "Context only.",
                },
            ),
        ]

        summary = rp.summarise_source_target_focusing(
            "candidate:semantic-1",
            [self.segment, segment2],
            records,
        )

        self.assertTrue(summary["focus_complete"])
        self.assertEqual(
            summary["answer_capable_segment_ids"],
            ["paper.pdf:source-segment-1"],
        )
        self.assertFalse(
            summary["negative_coverage_claim_authorised"]
        )

    def test_zero_answer_capable_does_not_authorise_absence(self):
        record = rp.build_source_target_focusing(
            "candidate:semantic-1",
            self.segment,
            {
                "state": "CONTEXT_ONLY",
                "reason": "Context only.",
            },
        )

        summary = rp.summarise_source_target_focusing(
            "candidate:semantic-1",
            [self.segment],
            [record],
        )

        self.assertTrue(summary["focus_complete"])
        self.assertEqual(summary["answer_capable_segment_ids"], [])
        self.assertFalse(
            summary["negative_coverage_claim_authorised"]
        )

    def test_incomplete_focus_is_recorded(self):
        summary = rp.summarise_source_target_focusing(
            "candidate:semantic-1",
            [self.segment],
            [],
        )

        self.assertFalse(summary["focus_complete"])
        self.assertEqual(
            summary["unfocused_segment_ids"],
            ["paper.pdf:source-segment-1"],
        )


if __name__ == "__main__":
    unittest.main()
