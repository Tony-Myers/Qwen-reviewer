"""Regression checks for Development mode isolation."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import server  # noqa: E402


SERVER_PATH = APP / "server.py"
CHAT_PATH = APP / "chat.html"
SERVER_TEXT = SERVER_PATH.read_text(encoding="utf-8")
CHAT_TEXT = CHAT_PATH.read_text(encoding="utf-8")
SERVER_TREE = ast.parse(SERVER_TEXT)


def function_node(name):
    for node in SERVER_TREE.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Function {name!r} not found")


def calls_in(function_name, called_name):
    node = function_node(function_name)
    found = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        func = item.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        if name == called_name:
            found.append(item)
    return found


class DevelopmentModeIsolation(unittest.TestCase):
    def test_parser_defaults_off(self):
        self.assertFalse(server._development_mode_enabled(None))
        self.assertFalse(server._development_mode_enabled(""))
        self.assertFalse(server._development_mode_enabled(object()))

    def test_parser_explicit_on_values(self):
        for value in ("1", "true", "on", "yes", " TRUE ", "On"):
            with self.subTest(value=value):
                self.assertTrue(server._development_mode_enabled(value))

    def test_parser_explicit_off_values(self):
        for value in ("0", "false", "off", "no", "garbage"):
            with self.subTest(value=value):
                self.assertFalse(server._development_mode_enabled(value))

    def test_start_review_declares_development_mode_form(self):
        node = function_node("start_review")
        names = [arg.arg for arg in node.args.args]
        self.assertIn("development_mode", names)

    def test_job_records_development_mode(self):
        node = function_node("start_review")
        source = ast.get_source_segment(SERVER_TEXT, node) or ""
        self.assertIn('"development_mode": want_development_mode', source)

    def test_trace_retention_is_mode_gated(self):
        node = function_node("_run_review_inner")
        source = ast.get_source_segment(SERVER_TEXT, node) or ""
        self.assertIn('if review_jobs[job_id].get("development_mode"):', source)
        self.assertIn('review_jobs[job_id]["trace"] = trace', source)

    def test_trace_endpoint_requires_mode(self):
        node = function_node("download_review_trace")
        source = ast.get_source_segment(SERVER_TEXT, node) or ""
        self.assertIn('job.get("development_mode")', source)
        self.assertIn('job.get("trace")', source)

    def test_ui_control_is_unchecked_by_default(self):
        self.assertIn('type="checkbox" id="developmentMode"', CHAT_TEXT)
        self.assertNotIn('type="checkbox" id="developmentMode" checked', CHAT_TEXT)

    def test_ui_sends_development_mode(self):
        self.assertIn(
            "fd.append('development_mode', "
            "document.getElementById('developmentMode').checked ? '1' : '0');",
            CHAT_TEXT,
        )

    def test_mode_not_passed_to_scientific_model_calls(self):
        forbidden = "development_mode"
        scientific_calls = (
            "review_chunk",
            "prepare_candidate_triage_evidence",
            "generate_candidate_propositions",
            "verify_candidate_propositions",
            "triage_candidate_findings",
            "synthesize_file_review",
            "synthesize_report",
            "validate_report_against_evidence",
        )
        for function_name in scientific_calls:
            calls = calls_in("_run_review_inner", function_name)
            self.assertTrue(calls, f"Expected call to {function_name}")
            for call in calls:
                rendered = ast.get_source_segment(SERVER_TEXT, call) or ""
                with self.subTest(call=function_name):
                    self.assertNotIn(forbidden, rendered)

    def test_observational_computations_not_mode_conditional(self):
        node = function_node("_run_review_inner")
        for item in ast.walk(node):
            if not isinstance(item, ast.If):
                continue
            condition = ast.get_source_segment(SERVER_TEXT, item.test) or ""
            if "development_mode" not in condition:
                continue
            body = "\n".join(
                ast.get_source_segment(SERVER_TEXT, child) or ""
                for child in item.body
            )
            self.assertNotIn("prepare_candidate_triage_evidence", body)
            self.assertNotIn("generate_candidate_propositions", body)
            self.assertNotIn("verify_candidate_propositions", body)
            self.assertNotIn("triage_candidate_findings", body)

    def test_trace_is_not_a_synthesis_input(self):
        for function_name in (
            "synthesize_file_review",
            "synthesize_report",
            "validate_report_against_evidence",
        ):
            for call in calls_in("_run_review_inner", function_name):
                rendered = ast.get_source_segment(SERVER_TEXT, call) or ""
                with self.subTest(call=function_name):
                    self.assertNotIn("trace", rendered)


if __name__ == "__main__":
    unittest.main()
