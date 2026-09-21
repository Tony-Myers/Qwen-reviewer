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
    "source_claims": [],
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
    "source_claims": [],
    "technical_claims": [],
}
empty_draft = ac.parse_academic_draft(json.dumps(empty))
check("empty references accepted", empty_draft.references == [])
check("empty technical claims accepted",
      empty_draft.technical_claims == [])



print("\n[8] local first pass uses the established model backend")
original_generate = ac.llm_backend.generate
original_make_sampler = ac.llm_backend.make_sampler
original_thinking = ac.llm_backend.thinking

calls = []
thinking_calls = []


class FakeThinking:
    def __init__(self, enabled):
        self.enabled = enabled

    def __enter__(self):
        thinking_calls.append(("enter", self.enabled))
        return None

    def __exit__(self, exc_type, exc, tb):
        thinking_calls.append(("exit", self.enabled))
        return False


def fake_thinking(enabled):
    return FakeThinking(enabled)


def fake_sampler(**kwargs):
    return {"fake_sampler": kwargs}


def fake_generate(model, tokenizer, prompt=None, **kwargs):
    calls.append({
        "model": model,
        "tokenizer": tokenizer,
        "prompt": prompt,
        "kwargs": kwargs,
    })
    return json.dumps(VALID)


try:
    ac.llm_backend.generate = fake_generate
    ac.llm_backend.make_sampler = fake_sampler
    ac.llm_backend.thinking = fake_thinking

    local_draft = ac.generate_academic_draft(
        "fake-model",
        "fake-tokenizer",
        "What is the relative efficiency formula for multiple imputation?",
        max_tokens=1800,
    )

finally:
    ac.llm_backend.generate = original_generate
    ac.llm_backend.make_sampler = original_make_sampler
    ac.llm_backend.thinking = original_thinking


check("local backend called exactly once", len(calls) == 1, calls)

if calls:
    sent = calls[0]
    prompt = sent["prompt"]

    check("system and user messages sent",
          isinstance(prompt, list)
          and len(prompt) == 2
          and prompt[0].get("role") == "system"
          and prompt[1].get("role") == "user",
          prompt)

    check("complete user question reaches local model",
          prompt[1].get("content")
          == "What is the relative efficiency formula for multiple imputation?",
          prompt[1] if len(prompt) > 1 else prompt)

    system_text = prompt[0].get("content", "")
    check("system prompt requires structured references",
          '"references"' in system_text,
          system_text[:500])

    check("system prompt requires technical claims",
          '"technical_claims"' in system_text,
          system_text[:500])

    check("system prompt prohibits model verification status",
          "application" in system_text.lower()
          and "verification status" in system_text.lower(),
          system_text[-500:])

    check("requested token budget passed through",
          sent["kwargs"].get("max_tokens") == 1800,
          sent["kwargs"])

check("thinking disabled for structural pass",
      thinking_calls == [("enter", False), ("exit", False)],
      thinking_calls)

check("generated structure is parsed",
      local_draft.references[0].author == "White"
      and local_draft.technical_claims[0].type == "formula")


print("\n[9] malformed local-model output fails conservatively")


def bad_generate(model, tokenizer, prompt=None, **kwargs):
    return '{"answer_draft": "broken"'


try:
    ac.llm_backend.generate = bad_generate
    ac.llm_backend.make_sampler = fake_sampler
    ac.llm_backend.thinking = fake_thinking

    try:
        ac.generate_academic_draft(
            "fake-model",
            "fake-tokenizer",
            "A valid question",
        )
    except ac.AcademicDraftError as exc:
        check("malformed model output is rejected",
              "not valid JSON" in str(exc),
              str(exc))
    else:
        check("malformed model output is rejected",
              False,
              "Expected AcademicDraftError.")

finally:
    ac.llm_backend.generate = original_generate
    ac.llm_backend.make_sampler = original_make_sampler
    ac.llm_backend.thinking = original_thinking


print("\n[10] empty questions never reach the model")
empty_calls = []


def should_not_generate(*args, **kwargs):
    empty_calls.append((args, kwargs))
    raise AssertionError("Model must not be called for an empty question.")


try:
    ac.llm_backend.generate = should_not_generate

    try:
        ac.generate_academic_draft(
            "fake-model",
            "fake-tokenizer",
            "   ",
        )
    except ac.AcademicDraftError as exc:
        check("empty question rejected locally",
              "question must be non-empty" in str(exc),
              str(exc))
    else:
        check("empty question rejected locally",
              False,
              "Expected AcademicDraftError.")

finally:
    ac.llm_backend.generate = original_generate

check("empty question caused no generation call",
      empty_calls == [],
      empty_calls)


print()
print("[11] source claims explicitly associate claims with proposed references")

source_claim_payload = dict(VALID)
source_claim_payload["source_claims"] = [
    {
        "claim": (
            "The number of imputations should reflect the "
            "fraction of missing information."
        ),
        "reference_index": 0,
    }
]

source_claim_draft = ac.parse_academic_draft(
    json.dumps(source_claim_payload)
)

check(
    "one source claim parsed",
    len(source_claim_draft.source_claims) == 1,
)
check(
    "source claim text retained",
    source_claim_draft.source_claims[0].claim
    == source_claim_payload["source_claims"][0]["claim"],
)
check(
    "source claim reference index retained",
    source_claim_draft.source_claims[0].reference_index == 0,
)

print()
print("[12] source claims must reference an existing proposed reference")

bad_source_reference = dict(VALID)
bad_source_reference["source_claims"] = [
    {
        "claim": "Synthetic source-supported claim.",
        "reference_index": 7,
    }
]

expect_error(
    "out-of-range source reference rejected",
    json.dumps(bad_source_reference),
    "reference_index must identify an existing reference",
)


negative_source_reference = dict(VALID)
negative_source_reference["source_claims"] = [
    {
        "claim": "Synthetic source-supported claim.",
        "reference_index": -1,
    }
]

expect_error(
    "negative source reference rejected",
    json.dumps(negative_source_reference),
    "reference_index must identify an existing reference",
)

boolean_source_reference = dict(VALID)
boolean_source_reference["source_claims"] = [
    {
        "claim": "Synthetic source-supported claim.",
        "reference_index": True,
    }
]

expect_error(
    "boolean source reference rejected",
    json.dumps(boolean_source_reference),
    "reference_index must be an integer",
)

print()
print("[13] local generation contract requires explicit source claims")

schema = ac.ACADEMIC_DRAFT_RESPONSE_FORMAT[
    "json_schema"
]["schema"]

check(
    "source_claims required by constrained schema",
    "source_claims" in schema["required"],
)
check(
    "source_claims defined by constrained schema",
    "source_claims" in schema["properties"],
)

source_schema = schema["properties"].get("source_claims", {})
source_item = source_schema.get("items", {})

check(
    "source claim schema requires claim and reference_index",
    set(source_item.get("required", []))
    == {"claim", "reference_index"},
)
check(
    "source claim schema prohibits additional fields",
    source_item.get("additionalProperties") is False,
)

prompt = ac.ACADEMIC_DRAFT_SYSTEM_PROMPT
normalized_prompt = " ".join(prompt.lower().split())

check(
    "system prompt requires source claims",
    '"source_claims"' in prompt,
)
check(
    "system prompt explains reference_index",
    "reference_index" in prompt,
)
check(
    "system prompt keeps source claims provisional",
    "source claims are proposals" in prompt.lower(),
)

check(
    "system prompt requires self-contained source claims",
    "self-contained propositions" in prompt.lower(),
)
check(
    "system prompt requires atomic source claims",
    "keep each source claim atomic" in prompt.lower(),
)
check(
    "system prompt limits source claims to literature-dependent propositions",
    "materially depend on the cited literature" in normalized_prompt,
)


print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)

print("All academic-chat tests passed.")
