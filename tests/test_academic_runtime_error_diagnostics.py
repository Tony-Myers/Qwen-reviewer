"""The Academic Chat RuntimeError diagnostic preserves the existing HTTP 502."""

import asyncio
import contextlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import server


class SyntheticReferenceError(RuntimeError):
    pass


def originating_reference_failure(*args, **kwargs):
    try:
        raise ValueError("synthetic underlying cause")
    except ValueError as exc:
        raise SyntheticReferenceError("synthetic reference failure") from exc


class BrokenDiagnosticStream:
    def write(self, text):
        raise OSError("synthetic stderr write failure")


def request_with_diagnostics(stream):
    with (
        patch.object(server, "ensure_model", return_value=None),
        patch.object(
            server.academic_reconciliation_orchestrator,
            "run_academic_reconciliation",
            side_effect=originating_reference_failure,
        ),
        contextlib.redirect_stderr(stream),
    ):
        return asyncio.run(server.academic_chat_first_stage({"question": "Test"}))


def assert_existing_response(response):
    assert response.status_code == 502
    assert json.loads(response.body) == {
        "error": "Academic reference service unavailable.",
        "detail": "synthetic reference failure",
    }


stream = io.StringIO()
response = request_with_diagnostics(stream)
assert_existing_response(response)
diagnostic = stream.getvalue()
assert "Traceback (most recent call last):" in diagnostic
assert "SyntheticReferenceError: synthetic reference failure" in diagnostic
assert "ValueError: synthetic underlying cause" in diagnostic
assert "originating_reference_failure" in diagnostic
assert "test_academic_runtime_error_diagnostics.py" in diagnostic
print("PASS: unchanged HTTP 502 payload and originating chained exception on stderr")

response = request_with_diagnostics(BrokenDiagnosticStream())
assert_existing_response(response)
print("PASS: diagnostic write failure preserves the existing HTTP 502 payload")
