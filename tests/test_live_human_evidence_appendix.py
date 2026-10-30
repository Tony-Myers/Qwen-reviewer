import unittest
from pathlib import Path


class LiveHumanEvidenceAppendixIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path("app/server.py").read_text()
        start = cls.source.index(
            "# --- Generate human-facing evidence appendix deterministically ---"
        )
        end = cls.source.index(
            "# Kept so the reviewer can ask where the paper says something.",
            start,
        )
        cls.integration = cls.source[start:end]

    def test_live_path_builds_cards_from_final_report(self):
        self.assertIn(
            "evidence_cards = build_evidence_cards(final_report)",
            self.integration,
        )

    def test_live_path_uses_human_renderer(self):
        self.assertIn(
            "appendix_lines = render_human_evidence_appendix(evidence_cards)",
            self.integration,
        )

    def test_live_path_does_not_supply_verified_relationships(self):
        self.assertNotIn("verified_relationships", self.integration)

    def test_live_path_does_not_use_technical_appendix_builder(self):
        self.assertNotIn("_build_appendix_text(", self.integration)

    def test_supplementary_source_chat_state_is_retained(self):
        self.assertIn(
            'review_jobs[job_id]["sources"] = citation_source',
            self.integration,
        )


if __name__ == "__main__":
    unittest.main()
