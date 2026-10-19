import unittest

from app import review_pipeline as rp


class SourceSubBlockTests(unittest.TestCase):

    def make_parent(self, text):
        return {
            "segment_id": "paper.pdf:source-segment-3",
            "source_name": "paper.pdf",
            "segment_index": 3,
            "start_char": 24000,
            "end_char": 24000 + len(text),
            "text": text,
        }

    def test_lossless_plain_text(self):
        text = "A" * 5100
        parent = self.make_parent(text)

        blocks = rp.build_source_sub_blocks(parent, max_chars=2000)
        coverage = rp.validate_source_sub_blocks(parent, blocks)

        self.assertTrue(coverage["complete"])
        self.assertEqual("".join(b["text"] for b in blocks), text)
        self.assertEqual(
            [len(b["text"]) for b in blocks],
            [2000, 2000, 1100],
        )

    def test_prefers_double_newline_boundary(self):
        text = ("A" * 900) + "\n\n" + ("B" * 900) + "\n\n" + ("C" * 900)
        parent = self.make_parent(text)

        blocks = rp.build_source_sub_blocks(parent, max_chars=1200)
        rp.validate_source_sub_blocks(parent, blocks)

        self.assertEqual("".join(b["text"] for b in blocks), text)
        self.assertTrue(blocks[0]["text"].endswith("\n\n"))

    def test_preserves_complete_table_markers(self):
        text = (
            "Intro text.\n\n"
            "[TABLE_START]\n"
            "Source: pdfplumber_text\n"
            "Page: 5\n"
            "Label: Table 4b\n"
            "Bodyfat\t−0.012\n"
            "[TABLE_END]\n"
            "\nFollowing prose."
        )
        parent = self.make_parent(text)

        blocks = rp.build_source_sub_blocks(parent, max_chars=100)
        coverage = rp.validate_source_sub_blocks(parent, blocks)

        self.assertTrue(coverage["complete"])
        self.assertEqual("".join(b["text"] for b in blocks), text)

    def test_absolute_offsets_are_parent_relative(self):
        text = "First paragraph.\n\nSecond paragraph."
        parent = self.make_parent(text)

        blocks = rp.build_source_sub_blocks(parent, max_chars=20)
        rp.validate_source_sub_blocks(parent, blocks)

        for block in blocks:
            self.assertEqual(
                block["source_start_char"],
                parent["start_char"] + block["parent_start_char"],
            )
            self.assertEqual(
                block["source_end_char"],
                parent["start_char"] + block["parent_end_char"],
            )

    def test_validator_rejects_modified_text(self):
        text = "A paragraph.\n\nAnother paragraph."
        parent = self.make_parent(text)
        blocks = rp.build_source_sub_blocks(parent, max_chars=20)

        blocks[0]["text"] = blocks[0]["text"] + "X"

        with self.assertRaises(ValueError):
            rp.validate_source_sub_blocks(parent, blocks)

    def test_validator_rejects_gap(self):
        text = "A" * 100
        parent = self.make_parent(text)
        blocks = rp.build_source_sub_blocks(parent, max_chars=50)

        blocks[1]["parent_start_char"] += 1

        with self.assertRaises(ValueError):
            rp.validate_source_sub_blocks(parent, blocks)


if __name__ == "__main__":
    unittest.main()
