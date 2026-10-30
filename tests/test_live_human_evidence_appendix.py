"""Static checks on the live wiring of the two appendices in server.py.

Behaviour is exercised in test_review_artefacts.py; these checks pin the
structure: the extraction evidence appendix and the Human Evidence Appendix
are built in separate blocks and stored under separate job keys.
"""
import unittest
from pathlib import Path


class LiveHumanEvidenceAppendixIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app/server.py").read_text()
        extraction_start = cls.source.index(
            "# --- Generate evidence appendix (in-memory, not written to disk) ---"
        )
        human_start = cls.source.index(
            "# --- Generate human-facing evidence appendix deterministically ---",
            extraction_start,
        )
        end = cls.source.index(
            "# Kept so the reviewer can ask where the paper says something.",
            human_start,
        )
        cls.extraction = cls.source[extraction_start:human_start]
        cls.integration = cls.source[human_start:end]

    def test_live_path_builds_cards_from_final_report(self):
        self.assertIn(
            "evidence_cards = build_evidence_cards(final_report)",
            self.integration,
        )

    def test_live_path_uses_human_renderer_with_unparsed_content(self):
        self.assertIn("render_human_evidence_appendix(", self.integration)
        self.assertIn(
            "unparsed_content=extract_unparsed_report_content(final_report)",
            self.integration,
        )

    def test_live_path_does_not_supply_verified_relationships(self):
        self.assertNotIn("verified_relationships", self.integration)

    def test_human_block_does_not_use_extraction_builder(self):
        self.assertNotIn("_build_appendix_text(", self.integration)

    def test_extraction_appendix_is_still_built(self):
        self.assertIn("appendix_lines = _build_appendix_text(", self.extraction)
        self.assertIn('sections.append(f"## Source: {name}', self.extraction)

    def test_artefacts_stored_under_separate_keys(self):
        self.assertIn('review_jobs[job_id]["appendix"] = appendix_lines', self.source)
        self.assertIn('review_jobs[job_id]["human_appendix"] = human_appendix', self.source)

    def test_supplementary_source_chat_state_is_retained(self):
        self.assertIn(
            'review_jobs[job_id]["sources"] = citation_source',
            self.extraction,
        )


if __name__ == "__main__":
    unittest.main()
