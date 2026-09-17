#!/usr/bin/env python3
"""Offline regression tests for the Academic Chat structured-output contract."""

import json
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import academic_chat as ac


fails = []


def check(label, condition, detail=None):
    if condition:
        print(f"  PASS  {label}")
        return
    print(f"  FAIL  {label}")
    if detail is not None:
        print(f"        {detail}")
    fails.append(label)


def expect_error(label, payload, contains):
    try:
        ac.parse_academic_draft(payload)
    except ac.AcademicDraftError as exc:
        check(label, contains in str(exc), str(exc))
    else:
        check(label, False, "Expected AcademicDraftError.")


VALID = {
    "answer_draft": (
        "The relative efficiency depends on the fraction of missing "
        "information and the number of imputations."
    ),
    "references": [
        {
            "title": (
                "Multiple imputation using chained equations: "
                "Issues and guidance for practice"
            ),
            "author": "White",
            "year": 2011,
            "venue": "Statistics in Medicine",
            "doi": None,
        }
    ],
    "technical_claims": [
        {
            "type": "formula",
            "concept": "multiple-imputation relative efficiency",
            "statement": "RE = (1 + lambda/m)^-1",
            "parameterisation": (
                "lambda = fraction of missing information"
            ),
        }
    ],
}


print("\n[1] valid structured output is accepted")
draft = ac.parse_academic_draft(json.dumps(VALID))

check("answer draft retained",
      draft.answer_draft.startswith("The relative efficiency"))
check("one reference parsed", len(draft.references) == 1)
check("reference title retained",
      draft.references[0].title == VALID["references"][0]["title"])
check("reference year retained",
      draft.references[0].year == 2011)
check("one technical claim parsed",
      len(draft.technical_claims) == 1)
check("technical statement retained",
      draft.technical_claims[0].statement
      == "RE = (1 + lambda/m)^-1")


print("\n[2] a simple Markdown JSON fence is tolerated")
fenced = "```json\n" + json.dumps(VALID) + "\n```"
fenced_draft = ac.parse_academic_draft(fenced)
check("fenced JSON parsed",
      fenced_draft.references[0].author == "White")


print("\n[3] malformed JSON is rejected rather than repaired")
expect_error(
    "broken JSON rejected",
    '{"answer_draft": "unfinished"',
    "not valid JSON",
)


print("\n[4] required top-level structure is enforced")
missing = dict(VALID)
missing.pop("technical_claims")
expect_error(
    "missing technical_claims rejected",
    json.dumps(missing),
    "missing required fields",
)

extra = dict(VALID)
extra["verified"] = True
expect_error(
    "model cannot add top-level verification status",
    json.dumps(extra),
    "unexpected fields",
)


print("\n[5] reference boundary is strict")
no_identity = dict(VALID)
no_identity["references"] = [
    {
        "title": None,
        "author": "Example",
        "year": 2020,
        "venue": "Example Journal",
        "doi": None,
    }
]
expect_error(
    "reference requires title or DOI",
    json.dumps(no_identity),
    "must contain a title or DOI",
)

bad_year = dict(VALID)
bad_year["references"] = [
    {
        "title": "Example article",
        "author": "Example",
        "year": "2020",
        "venue": "Example Journal",
        "doi": None,
    }
]
expect_error(
    "reference year must be integer or null",
    json.dumps(bad_year),
    "year must be an integer or null",
)

reference_verified = dict(VALID)
reference_verified["references"] = [
    {
        "title": "Example article",
        "author": "Example",
        "year": 2020,
        "venue": "Example Journal",
        "doi": None,
        "verified": True,
    }
]
expect_error(
    "model cannot mark a reference verified",
    json.dumps(reference_verified),
    "unexpected fields",
)


print("\n[6] technical claims are captured but cannot self-verify")
technical_verified = dict(VALID)
technical_verified["technical_claims"] = [
    {
        "type": "formula",
        "concept": "example",
        "statement": "x = y",
        "parameterisation": None,
        "technically_verified": True,
    }
]
expect_error(
    "model cannot mark a technical claim verified",
    json.dumps(technical_verified),
    "unexpected fields",
)

missing_statement = dict(VALID)
missing_statement["technical_claims"] = [
    {
        "type": "formula",
        "concept": "example",
        "parameterisation": None,
    }
]
expect_error(
    "technical statement is required",
    json.dumps(missing_statement),
    "statement must be a non-empty string",
)


print("\n[7] empty arrays are valid")
empty = {
    "answer_draft": "No references or technical claims are proposed.",
    "references": [],
    "technical_claims": [],
}
empty_draft = ac.parse_academic_draft(json.dumps(empty))
check("empty references accepted", empty_draft.references == [])
check("empty technical claims accepted",
      empty_draft.technical_claims == [])


print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)

print("All academic-chat tests passed.")
