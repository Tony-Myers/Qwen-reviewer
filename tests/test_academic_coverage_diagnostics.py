#!/usr/bin/env python3
"""Failure-only global coverage diagnostics, using the real decoding/validation path."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import academic_claim_assessor as adapter
import academic_claim_coverage as coverage
import academic_orchestrator as orchestrator
import academic_reconciliation_orchestrator as reconciliation
import llm_backend
import server


class CoverageDiagnosticsTests(unittest.TestCase):
    answer = "A larger sample can improve precision. PRIVATE ANSWER SENTINEL."
    expected = {
        "status": "coverage_assessment_unavailable",
        "missing_claims": None,
        "reasons": ["Local claim-coverage output could not be validated."],
    }

    def run_coverage(self, output=None, error=None, *, global_only=False):
        stderr = io.StringIO()
        with patch.object(llm_backend, "generate", return_value=output,
                          side_effect=(error if error else (
                              [output, '{"discovered_claims": []}',
                               '{"discovered_claims": []}'] if global_only else None))) as generate:
            with contextlib.redirect_stderr(stderr):
                result = server.assess_academic_claim_coverage(
                    answer_draft=self.answer, existing_claims=[])
        return result, stderr.getvalue(), generate.call_count

    def assert_failure(self, result, logged, *, partial=False):
        expected = dict(self.expected, missing_claims=[]) if partial else self.expected
        self.assertEqual(result.to_dict(), expected)
        release = orchestrator.assess_academic_release([], claim_coverage=result)
        self.assertEqual(release.status, "checking_incomplete")
        presentation = reconciliation.decide_presentation(release, revised=False)
        self.assertEqual(presentation.to_dict(), {
            "mode": "qualified", "reason": "checking_incomplete"})
        self.assertIn(
            "[claim-coverage] global discovery item rejected" if partial
            else "[claim-coverage] global discovery failed", logged)
        self.assertNotIn("PRIVATE ANSWER SENTINEL", logged)
        self.assertNotIn("ANSWER DRAFT", logged)
        self.assertNotIn("raw assessor", json.dumps(result.to_dict()))

    def test_backend_cause_chain_without_output(self):
        cause = OSError("synthetic connection failure")
        error = llm_backend.BackendError("synthetic inference failure")
        error.__cause__ = cause
        result, logged, count = self.run_coverage(error=error)
        self.assert_failure(result, logged)
        self.assertEqual(count, 1)
        self.assertIn("BackendError: synthetic inference failure", logged)
        self.assertIn("OSError: synthetic connection failure", logged)
        self.assertNotIn("raw assessor output:", logged)

    def test_malformed_json_and_non_object_output(self):
        for raw, detail in [('{"discovered_claims": [', "JSONDecodeError"),
                            ('[]', "must decode to a JSON object"),
                            ('', "JSONDecodeError")]:
            with self.subTest(raw=raw):
                result, logged, count = self.run_coverage(raw)
                self.assert_failure(result, logged)
                self.assertEqual(count, 1)
                self.assertIn("ClaimAssessorOutputError", logged)
                self.assertIn(detail, logged)
                self.assertIn(f"raw assessor output: {raw!r}", logged)

    def test_contract_and_application_validation(self):
        item = dict(type="methodological", concept="precision",
                    statement="A larger sample can improve precision.",
                    parameterisation=None, source_anchor="absent anchor")
        cases = [
            ({"missing_claims": []}, "must contain exactly 'discovered_claims'"),
            ({"discovered_claims": "wrong type"}, "must be an array"),
            ({"discovered_claims": [item]}, "verbatim contiguous span"),
            ({"discovered_claims": [dict(item, source_anchor="A")]},
             "must occur exactly once"),
            ({"discovered_claims": [dict(item, parameterisation="")]},
             "parameterisation must be non-empty text or null"),
        ]
        for proposal, detail in cases:
            with self.subTest(detail=detail):
                raw = json.dumps(proposal, indent=2)
                result, logged, count = self.run_coverage(raw, global_only=True)
                partial = isinstance(proposal.get("discovered_claims"), list)
                self.assert_failure(result, logged, partial=partial)
                self.assertEqual(count, 3 if partial else 1)
                self.assertIn(detail, logged)
                self.assertIn(f"raw assessor output: {raw!r}", logged)

    def test_successful_coverage_is_silent(self):
        result, logged, count = self.run_coverage(
            '{"discovered_claims": []}')
        self.assertEqual(result.status, coverage.COVERAGE_STATUS_NO_MISSING_PROPOSED)
        self.assertEqual(count, 3)  # Discovery and two sentence audits.
        self.assertEqual(logged, "")

    def test_success_and_additive_failures_are_silent(self):
        # Global discovery succeeds; malformed sentence audits keep their
        # existing fail-open behaviour and must not log their raw responses.
        stderr = io.StringIO()
        with patch.object(llm_backend, "generate", side_effect=[
                '{"discovered_claims": []}', 'BAD AUDIT ONE', 'BAD AUDIT TWO']):
            with contextlib.redirect_stderr(stderr):
                result = server.assess_academic_claim_coverage(
                    answer_draft=self.answer, existing_claims=[])
        self.assertEqual(result.status, coverage.COVERAGE_STATUS_NO_MISSING_PROPOSED)
        self.assertEqual(stderr.getvalue(), "")
        # A subsequent failure must not log stale output from that success.
        result, logged, _ = self.run_coverage(error=llm_backend.BackendError("next"))
        self.assert_failure(result, logged)
        self.assertNotIn("raw assessor output:", logged)

    def test_unrelated_adapter_errors_are_unchanged_and_silent(self):
        for error in [llm_backend.BackendError("unrelated backend"),
                      TypeError("unrelated programming")]:
            stderr = io.StringIO()
            with patch.object(llm_backend, "generate", side_effect=error):
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(type(error)) as raised:
                        adapter.generate_claim_assessor_output(None, None, "PRIVATE PROMPT", {})
            self.assertIs(raised.exception, error)
            self.assertEqual(stderr.getvalue(), "")
        with patch.object(llm_backend, "generate", return_value="UNRELATED RAW"):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(adapter.ClaimAssessorOutputError):
                    adapter.generate_claim_assessor_output(None, None, "PRIVATE PROMPT", {})
        self.assertEqual(stderr.getvalue(), "")

    def test_programming_errors_propagate_unchanged(self):
        for error in [TypeError("programming"), ValueError("programming")]:
            stderr = io.StringIO()
            with patch.object(llm_backend, "generate", side_effect=error):
                with contextlib.redirect_stderr(stderr):
                    with self.assertRaises(type(error)) as raised:
                        server.assess_academic_claim_coverage(
                            answer_draft=self.answer, existing_claims=[])
            self.assertIs(raised.exception, error)
            self.assertEqual(stderr.getvalue(), "")

    def test_outer_backend_error_keeps_existing_result(self):
        with patch.object(coverage, "assess_claim_coverage_two_stage",
                          side_effect=llm_backend.BackendError("outside adapter")):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                result = server.assess_academic_claim_coverage(
                    answer_draft=self.answer, existing_claims=[])
        self.assertEqual(result.reasons, ["Local claim-coverage inference was unavailable."])
        self.assertEqual(stderr.getvalue(), "")

    def test_logging_failure_does_not_change_result(self):
        class BrokenLog:
            def write(self, text):
                raise OSError("log unavailable")
        with patch.object(llm_backend, "generate", return_value="INVALID"):
            with contextlib.redirect_stderr(BrokenLog()):
                result = server.assess_academic_claim_coverage(
                    answer_draft=self.answer, existing_claims=[])
        self.assertEqual(result.to_dict(), self.expected)


if __name__ == "__main__":
    unittest.main()
