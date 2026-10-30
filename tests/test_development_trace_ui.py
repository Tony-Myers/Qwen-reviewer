import unittest
from pathlib import Path


class DevelopmentTraceUI(unittest.TestCase):
    """Source-presence checks only. Behaviour (envelope unwrapping, job-bound
    caching, separate appendices) is executed in test_chat_artefact_behaviour.py."""

    @classmethod
    def setUpClass(cls):
        cls.source = Path("app/chat.html").read_text()

    def check(self, text):
        self.assertIn(text, self.source)
    def test_completion_and_default_gate(self):
        self.check("showReport(d.report, d.has_appendix, job_id, d.has_development_trace, d.has_human_appendix);")
        self.check("function showReport(md, hasAppendix, jobId, hasDevelopmentTrace = false, hasHumanAppendix = false)")

    def test_trace_controls_and_endpoint(self):
        self.check("if (hasDevelopmentTrace) {")
        self.check("developmentTraceToggle")
        self.check("/api/review/trace/")

    def test_readable_sections(self):
        for text in ("<details", "<summary><strong>", "Source processing", "Finding development", "Methodological propositions", "Proposition verification", "Candidate triage", "File synthesis", "Final synthesis &amp; validation", "Final assembly"):
            self.check(text)

    def test_confidentiality_and_missing_data(self):
        self.check("may contain manuscript text, model outputs and internal diagnostics")
        self.check("Not available for this run.")

    def test_full_json_download(self):
        self.check("JSON.stringify(trace, null, 2)")
        self.check("development-trace.json")


if __name__ == "__main__":
    unittest.main()
