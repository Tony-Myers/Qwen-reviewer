import unittest

from app import review_pipeline as rp


def segments():
    source = (
        "Participants were recruited from schools. "
        "The intervention lasted sixteen weeks. "
        "A mixed-effects model was fitted."
    )
    return rp.build_searchable_source_segments(
        "paper.pdf",
        source,
        max_chars=40,
    )


def screening(segment, state, premise_id="candidate:semantic-1"):
    return {
        "assessment_type": "source_target_segment_screening",
        "premise_id": premise_id,
        "segment_id": segment["segment_id"],
        "state": state,
        "reason": "Controlled screening result.",
    }


class SourceTargetSegmentScreeningTests(unittest.TestCase):

    def test_schema_has_only_screening_states(self):
        schema = rp.source_target_screening_output_schema()
        states = set(
            schema["properties"]["state"]["enum"]
        )
        self.assertEqual(
            states,
            {
                "POTENTIALLY_RELEVANT",
                "NO_RELEVANT_INFORMATION",
            },
        )

    def test_build_accepts_potentially_relevant(self):
        segment = segments()[0]
        result = rp.build_source_target_screening(
            "candidate:semantic-1",
            segment,
            {
                "state": "POTENTIALLY_RELEVANT",
                "reason": "Contains design information.",
            },
        )
        self.assertEqual(result["state"], "POTENTIALLY_RELEVANT")
        self.assertEqual(result["segment_id"], segment["segment_id"])

    def test_build_accepts_no_relevant_information(self):
        segment = segments()[0]
        result = rp.build_source_target_screening(
            "candidate:semantic-1",
            segment,
            {
                "state": "NO_RELEVANT_INFORMATION",
                "reason": "Does not address the requested information.",
            },
        )
        self.assertEqual(result["state"], "NO_RELEVANT_INFORMATION")

    def test_build_rejects_absence_state(self):
        segment = segments()[0]
        with self.assertRaises(ValueError):
            rp.build_source_target_screening(
                "candidate:semantic-1",
                segment,
                {
                    "state": "MANUSCRIPT_UNRESOLVED",
                    "reason": "Not found.",
                },
            )

    def test_complete_screening_is_recorded(self):
        source_segments = segments()
        records = [
            screening(
                segment,
                "POTENTIALLY_RELEVANT"
                if i == 1
                else "NO_RELEVANT_INFORMATION",
            )
            for i, segment in enumerate(source_segments)
        ]

        result = rp.summarise_exhaustive_source_target_screening(
            "candidate:semantic-1",
            source_segments,
            records,
        )

        self.assertTrue(result["screen_complete"])
        self.assertEqual(
            result["segments_screened"],
            result["segments_total"],
        )
        self.assertEqual(
            result["potentially_relevant_segment_ids"],
            [source_segments[1]["segment_id"]],
        )

    def test_incomplete_screening_is_not_complete(self):
        source_segments = segments()
        records = [
            screening(
                source_segments[0],
                "NO_RELEVANT_INFORMATION",
            )
        ]

        result = rp.summarise_exhaustive_source_target_screening(
            "candidate:semantic-1",
            source_segments,
            records,
        )

        self.assertFalse(result["screen_complete"])
        self.assertGreater(
            len(result["unscreened_segment_ids"]),
            0,
        )

    def test_duplicate_screen_is_rejected(self):
        source_segments = segments()
        record = screening(
            source_segments[0],
            "NO_RELEVANT_INFORMATION",
        )

        with self.assertRaises(ValueError):
            rp.summarise_exhaustive_source_target_screening(
                "candidate:semantic-1",
                source_segments,
                [record, dict(record)],
            )

    def test_unknown_segment_is_rejected(self):
        source_segments = segments()
        record = screening(
            source_segments[0],
            "NO_RELEVANT_INFORMATION",
        )
        record["segment_id"] = "paper.pdf:source-segment-999"

        with self.assertRaises(ValueError):
            rp.summarise_exhaustive_source_target_screening(
                "candidate:semantic-1",
                source_segments,
                [record],
            )

    def test_wrong_premise_is_rejected(self):
        source_segments = segments()
        record = screening(
            source_segments[0],
            "NO_RELEVANT_INFORMATION",
            premise_id="different:semantic-1",
        )

        with self.assertRaises(ValueError):
            rp.summarise_exhaustive_source_target_screening(
                "candidate:semantic-1",
                source_segments,
                [record],
            )

    def test_summary_has_no_manuscript_absence_state(self):
        source_segments = segments()
        records = [
            screening(
                segment,
                "NO_RELEVANT_INFORMATION",
            )
            for segment in source_segments
        ]

        result = rp.summarise_exhaustive_source_target_screening(
            "candidate:semantic-1",
            source_segments,
            records,
        )

        self.assertTrue(result["screen_complete"])
        self.assertNotIn("state", result)
        self.assertNotIn("manuscript_unresolved", result)


if __name__ == "__main__":
    unittest.main()
