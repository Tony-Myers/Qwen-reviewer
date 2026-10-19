import unittest

from app import review_pipeline as rp


class SearchableSourceSegmentTests(unittest.TestCase):

    def test_short_source_is_one_exact_segment(self):
        source = "Alpha\n\nBeta\nGamma"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=100
        )

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["start_char"], 0)
        self.assertEqual(segments[0]["end_char"], len(source))
        self.assertEqual(segments[0]["text"], source)

    def test_long_source_is_losslessly_partitioned(self):
        source = "abcdefghijklmnopqrstuvwxyz"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=7
        )

        self.assertEqual(
            "".join(segment["text"] for segment in segments),
            source,
        )
        self.assertEqual(
            [(s["start_char"], s["end_char"]) for s in segments],
            [(0, 7), (7, 14), (14, 21), (21, 26)],
        )

    def test_whitespace_is_preserved_exactly(self):
        source = "  A\n\n\nB\t C  \n"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=4
        )

        self.assertEqual(
            "".join(segment["text"] for segment in segments),
            source,
        )

    def test_ids_are_deterministic(self):
        source = "abcdefghij"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=4
        )

        self.assertEqual(
            [segment["segment_id"] for segment in segments],
            [
                "paper.pdf:source-segment-1",
                "paper.pdf:source-segment-2",
                "paper.pdf:source-segment-3",
            ],
        )

    def test_validation_certifies_complete_exact_coverage(self):
        source = "abcdefghij"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=4
        )

        result = rp.validate_searchable_source_segments(
            "paper.pdf", source, segments
        )

        self.assertEqual(result["assessment_type"],
                         "searchable_source_coverage")
        self.assertEqual(result["source_chars"], len(source))
        self.assertEqual(result["covered_chars"], len(source))
        self.assertEqual(result["segment_count"], 3)
        self.assertTrue(result["complete"])

    def test_validation_rejects_gap(self):
        source = "abcdefghij"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=5
        )
        segments[1]["start_char"] = 6
        segments[1]["text"] = source[6:10]

        with self.assertRaises(ValueError):
            rp.validate_searchable_source_segments(
                "paper.pdf", source, segments
            )

    def test_validation_rejects_overlap(self):
        source = "abcdefghij"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=5
        )
        segments[1]["start_char"] = 4
        segments[1]["text"] = source[4:10]

        with self.assertRaises(ValueError):
            rp.validate_searchable_source_segments(
                "paper.pdf", source, segments
            )

    def test_validation_rejects_modified_text(self):
        source = "abcdefghij"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=5
        )
        segments[0]["text"] = "XXXXX"

        with self.assertRaises(ValueError):
            rp.validate_searchable_source_segments(
                "paper.pdf", source, segments
            )

    def test_validation_rejects_truncated_coverage(self):
        source = "abcdefghij"
        segments = rp.build_searchable_source_segments(
            "paper.pdf", source, max_chars=5
        )

        with self.assertRaises(ValueError):
            rp.validate_searchable_source_segments(
                "paper.pdf", source, segments[:-1]
            )

    def test_empty_source_is_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_searchable_source_segments(
                "paper.pdf", "", max_chars=5
            )


if __name__ == "__main__":
    unittest.main()
