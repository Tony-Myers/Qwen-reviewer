"""Isolated regressions for comprehensive table-page vision."""

import unittest
from pathlib import Path
from unittest.mock import patch

import review_pipeline as rp


class ComprehensiveTableVisionTests(unittest.TestCase):

    def block(self, page, body="A\tB\n1\t2"):
        return (
            page,
            "[TABLE_START]\n"
            "Source: pdfplumber\n"
            f"Page: {page}\n"
            f"{body}\n"
            "[TABLE_END]",
        )

    def test_reads_each_unique_table_page_once_and_preserves_text_blocks(self):
        original = [
            self.block(3),
            self.block(3, "C\tD\n3\t4"),
            self.block(7),
        ]

        calls = []

        def render(path, page, dpi):
            calls.append(("render", page))
            return f"png-{page}".encode()

        def describe(png, prompt):
            page = int(png.decode().split("-")[1])
            calls.append(("describe", page))
            return f"Header | Value\nrow | {page}"

        with patch.object(rp, "_render_page_png", side_effect=render), \
             patch("llm_backend.vision_available", return_value=True), \
             patch("llm_backend.describe_image", side_effect=describe):
            result, notes = rp.read_all_table_pages_with_vision(
                Path("paper.pdf"), original
            )

        self.assertEqual(result[:3], original)
        self.assertEqual(
            calls,
            [
                ("render", 3),
                ("describe", 3),
                ("render", 7),
                ("describe", 7),
            ],
        )

        visual = result[3:]
        self.assertEqual([page for page, _ in visual], [3, 7])
        self.assertTrue(all("Source: vision" in block for _, block in visual))
        self.assertTrue(
            all(
                "Acquisition state: vision_transcribed" in block
                for _, block in visual
            )
        )
        self.assertIn("2/2 unique extracted table page(s)", notes[0])

    def test_does_not_use_damage_detector_as_gate(self):
        original = [self.block(11)]

        with patch.object(
            rp, "table_looks_damaged",
            side_effect=AssertionError("damage detector must not be called"),
        ), patch.object(
            rp, "_render_page_png", return_value=b"png"
        ), patch(
            "llm_backend.vision_available", return_value=True
        ), patch(
            "llm_backend.describe_image", return_value="A | B\n1 | 2"
        ):
            result, _ = rp.read_all_table_pages_with_vision(
                Path("paper.pdf"), original
            )

        self.assertEqual(len(result), 2)
        self.assertIn("Source: vision", result[1][1])

    def test_unusable_visual_reading_does_not_remove_text_evidence(self):
        original = [self.block(5)]

        with patch.object(
            rp, "_render_page_png", return_value=b"png"
        ), patch(
            "llm_backend.vision_available", return_value=True
        ), patch(
            "llm_backend.describe_image", return_value=""
        ):
            result, notes = rp.read_all_table_pages_with_vision(
                Path("paper.pdf"), original
            )

        self.assertEqual(result, original)
        self.assertTrue(
            any("vision_empty: page(s) 5" in note for note in notes)
        )

    def test_no_table_response_has_distinct_acquisition_state(self):
        original = [self.block(6)]

        with patch.object(
            rp, "_render_page_png", return_value=b"png"
        ), patch(
            "llm_backend.vision_available", return_value=True
        ), patch(
            "llm_backend.describe_image",
            return_value="No table on this page",
        ):
            result, notes = rp.read_all_table_pages_with_vision(
                Path("paper.pdf"), original
            )

        self.assertEqual(result, original)
        self.assertTrue(
            any(
                "vision_reported_no_table: page(s) 6" in note
                for note in notes
            )
        )

    def test_render_failure_has_distinct_acquisition_state(self):
        original = [self.block(8)]

        with patch.object(
            rp, "_render_page_png", return_value=b""
        ), patch(
            "llm_backend.vision_available", return_value=True
        ), patch(
            "llm_backend.describe_image"
        ) as describe:
            result, notes = rp.read_all_table_pages_with_vision(
                Path("paper.pdf"), original
            )

        describe.assert_not_called()
        self.assertEqual(result, original)
        self.assertTrue(
            any("render_failed: page(s) 8" in note for note in notes)
        )

    def test_existing_vision_block_is_not_reread(self):
        visual = (
            4,
            "[TABLE_START]\nSource: vision\nPage: 4\nA | B\n1 | 2\n"
            "[TABLE_END]",
        )

        with patch(
            "llm_backend.vision_available", return_value=True
        ), patch.object(
            rp, "_render_page_png"
        ) as render:
            result, notes = rp.read_all_table_pages_with_vision(
                Path("paper.pdf"), [visual]
            )

        render.assert_not_called()
        self.assertEqual(result, [visual])
        self.assertTrue(any("no usable table page numbers" in n for n in notes))

    def test_empty_input_is_unchanged(self):
        result, notes = rp.read_all_table_pages_with_vision(
            Path("paper.pdf"), []
        )
        self.assertEqual(result, [])
        self.assertTrue(notes)


if __name__ == "__main__":
    unittest.main()
