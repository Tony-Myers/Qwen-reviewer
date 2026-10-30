"""Behavioural tests for the review artefact controls in app/chat.html.

The page's own JavaScript functions are executed by
tests/js/chat_artefact_harness.js under Node.js, against a fake DOM and a
controllable fake fetch. Every response is synthetic. No browser, server,
network or model is used. The tests are skipped when Node.js is not installed.

Covered:
- the development-trace endpoint envelope {trace, filename} is unwrapped
  before rendering and download, and malformed bodies are rejected;
- a delayed trace or appendix response for job A is never displayed, cached
  or returned for a later job B, whether B has Development mode on or off,
  and whether the fetch or the response body arrives late;
- the extraction evidence appendix and the Human Evidence Appendix are
  separate controls, endpoints, sections and downloads.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "js" / "chat_artefact_harness.js"
CHAT = ROOT / "app" / "chat.html"
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required to execute the chat.html functions")
class ChatArtefactBehaviour(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        completed = subprocess.run(
            [NODE, str(HARNESS), str(CHAT)],
            cwd=ROOT, capture_output=True, text=True, timeout=60, check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        cls.results = json.loads(completed.stdout)

    def scenario(self, name):
        result = self.results[name]
        self.assertNotIn("error", result, result.get("error") if isinstance(result, dict) else result)
        return result

    # --- Trace envelope ----------------------------------------------
    def test_trace_envelope_is_unwrapped_for_rendering(self):
        result = self.scenario("envelope_rendering")
        self.assertTrue(result["displays_source_name"])
        self.assertTrue(result["displays_source_chunk"])
        self.assertFalse(result["displays_no_per_file_message"])

    def test_trace_download_is_the_inner_trace(self):
        result = self.scenario("envelope_rendering")
        self.assertTrue(result["download_is_inner_trace"])
        self.assertEqual(result["download_name"], "development-trace.json")
        self.assertTrue(result["second_fetch_used_cache"])

    def test_malformed_or_foreign_trace_bodies_are_rejected(self):
        result = self.scenario("malformed_envelope")
        for case in ("missing_trace", "array_trace", "string_trace", "other_job_trace"):
            with self.subTest(case=case):
                self.assertTrue(result[case]["reported_unavailable"])
                self.assertFalse(result[case]["rendered_trace_view"])

    # --- Cross-job race ----------------------------------------------
    def test_late_trace_for_job_a_is_not_used_for_job_b_with_trace(self):
        result = self.scenario("late_response_after_switch_on")
        for timing in ("late_fetch", "late_body"):
            with self.subTest(timing=timing):
                observed = result[timing]
                self.assertEqual(observed["current_job"], "FAKE-B")
                self.assertFalse(observed["b_section_shows_a"])
                self.assertTrue(observed["b_requested_own_trace"])
                self.assertEqual(observed["b_received_job"], "FAKE-B")
                self.assertEqual(observed["b_download_job"], "FAKE-B")

    def test_late_trace_for_job_a_is_not_used_for_job_b_without_trace(self):
        result = self.scenario("late_response_after_switch_off")
        self.assertEqual(result["current_job"], "FAKE-B")
        self.assertFalse(result["b_has_trace_controls"])
        self.assertFalse(result["b_page_shows_a"])
        self.assertTrue(result["b_requested_own_trace"])
        self.assertIsNone(result["b_received_job"])
        self.assertEqual(result["downloads"], 0)

    def test_late_appendix_for_job_a_is_not_used_for_job_b(self):
        result = self.scenario("late_appendix_after_switch")
        for kind in ("extraction", "human"):
            with self.subTest(kind=kind):
                observed = result[kind]
                self.assertIsInstance(observed, dict)
                self.assertFalse(observed["b_section_shows_a"])
                self.assertTrue(observed["b_requested_own"])
                self.assertEqual(observed["b_received"], "Appendix text for job B")

    # --- Two separate appendices -----------------------------------------
    def test_both_appendices_have_separate_controls(self):
        result = self.scenario("two_appendices")
        self.assertNotIn("human_functions_missing", result)
        for control, present in result["controls_present"].items():
            with self.subTest(control=control):
                self.assertTrue(present)
        self.assertEqual(result["labels"]["appendixToggle"], "Show extraction evidence appendix")
        self.assertEqual(result["labels"]["humanAppendixToggle"], "Show Human Evidence Appendix")

    def test_both_appendices_load_from_their_own_endpoints(self):
        result = self.scenario("two_appendices")
        self.assertTrue(result["extraction_section"])
        self.assertTrue(result["human_section"])
        self.assertFalse(result["extraction_section_has_human"])
        self.assertEqual(
            result["download_names"],
            ["review_evidence_appendix.md", "review_human_evidence_appendix.md"],
        )
        self.assertIn("Synthetic extraction A", result["download_bodies"][0])
        self.assertIn("Synthetic cards A", result["download_bodies"][1])


if __name__ == "__main__":
    unittest.main()
