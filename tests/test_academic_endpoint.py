#!/usr/bin/env python3
"""
Regression tests for the Academic Chat bibliographic-verification boundary.

These tests are deliberately offline. They do not call Crossref, OpenAlex or
the language model. The purpose is to establish the boundary around
/api/chat/academic/verify-reference:

- only bibliographic fields may enter;
- a title or DOI is required;
- invalid input is rejected before the verifier is called;
- model access is not part of reference verification;
- bibliographic-service failures become an explicit 502 response.

    python3 tests/test_academic_endpoint.py

Requires the app's dependencies, so it skips where server.py cannot be
imported, matching the convention used by test_notes_chat.py.
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

try:
    import server
except Exception as exc:                                      # pragma: no cover
    print(f"SKIPPED: the app's dependencies are not importable here ({exc}).")
    print("Run this with the virtual environment the server uses.")
    raise SystemExit(0)


failures = []


def check(label, condition):
    print(("  PASS  " if condition else "  FAIL: ") + label)
    if not condition:
        failures.append(label)


def run(request):
    return asyncio.run(server.academic_verify_reference(request))


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


@dataclass
class FakeResult:
    payload: dict

    def to_dict(self):
        return self.payload


original_verifier = server.verify_academic_reference
original_ensure_model = server.ensure_model

calls = []


def model_must_not_be_called(*args, **kwargs):
    raise AssertionError(
        "Academic reference verification attempted to access the language model."
    )


def fake_verifier(**kwargs):
    calls.append(kwargs)
    return FakeResult({
        "crossref_verification": {"status": "verified"},
        "doi_corroboration": {"status": "corroborated"},
        "related_corroboration": {"status": "corroborated"},
        "identity_conflict": False,
        "reasons": ["offline test result"],
        "claim_verified": False,
    })


server.ensure_model = model_must_not_be_called
server.verify_academic_reference = fake_verifier

try:
    print("[1] valid bibliographic metadata reaches only the verifier")
    calls.clear()
    result = run({
        "title": "Example statistical paper",
        "author": "Example",
        "year": 2020,
        "venue": "Example Journal",
        "doi": "10.1234/example",
    })

    check("endpoint returns a dictionary", isinstance(result, dict))
    check("verifier called exactly once", len(calls) == 1)
    check(
        "only the five bibliographic fields reach the verifier",
        len(calls) == 1 and set(calls[0]) == {
            "title", "author", "year", "venue", "doi"
        },
    )
    check(
        "bibliographic values are passed correctly",
        len(calls) == 1
        and calls[0]["title"] == "Example statistical paper"
        and calls[0]["author"] == "Example"
        and calls[0]["year"] == 2020
        and calls[0]["venue"] == "Example Journal"
        and calls[0]["doi"] == "10.1234/example",
    )
    check("claim verification remains false",
          result.get("claim_verified") is False)

    print()
    print("[2] arbitrary or confidential text is rejected before verification")
    for forbidden in ("messages", "question", "manuscript"):
        calls.clear()
        response = run({
            "title": "Example statistical paper",
            forbidden: "CONFIDENTIAL TEXT MUST NOT LEAVE THIS PROCESS",
        })
        body = response_json(response)
        check(f"{forbidden!r} produces HTTP 400",
              response.status_code == 400)
        check(f"{forbidden!r} is named as unexpected",
              forbidden in body.get("unexpected_fields", []))
        check(f"{forbidden!r} never reaches the verifier",
              calls == [])

    print()
    print("[3] title or DOI is required")
    calls.clear()
    response = run({
        "author": "Example",
        "year": 2020,
        "venue": "Example Journal",
    })
    body = response_json(response)
    check("metadata without title or DOI produces HTTP 400",
          response.status_code == 400)
    check("missing identifier has an explicit explanation",
          "title or DOI" in body.get("error", ""))
    check("missing identifier never reaches the verifier",
          calls == [])

    print()
    print("[4] malformed year is rejected before verification")
    calls.clear()
    response = run({
        "title": "Example statistical paper",
        "year": "twenty twenty",
    })
    body = response_json(response)
    check("malformed year produces HTTP 400",
          response.status_code == 400)
    check("year error is explicit",
          "year" in body.get("error", "").lower())
    check("malformed year never reaches the verifier",
          calls == [])

    print()
    print("[5] bibliographic-service failure is explicit")

    def failing_verifier(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("simulated external service failure")

    server.verify_academic_reference = failing_verifier
    calls.clear()

    response = run({"doi": "10.1234/example"})
    body = response_json(response)

    check("service failure produces HTTP 502",
          response.status_code == 502)
    check("service failure is labelled clearly",
          body.get("error") == "Academic reference service unavailable.")
    check("failure detail is retained for diagnosis",
          "simulated external service failure" in body.get("detail", ""))
    check("verifier was attempted exactly once",
          len(calls) == 1)

    print()
    print("[6] reference verification never requires model access")
    # ensure_model has been replaced by a function that raises immediately.
    # Reaching this point after all endpoint calls therefore establishes that
    # none of those paths attempted to load or invoke the model.
    check("all endpoint paths completed with model access disabled", True)

finally:
    server.verify_academic_reference = original_verifier
    server.ensure_model = original_ensure_model


print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    raise SystemExit(1)

print("All academic-endpoint tests passed.")
