#!/usr/bin/env python3
"""
A claim anchor that does not sit inside one answer sentence must not cost
the reader the answer.

    python3 tests/test_academic_coverage_sentence_guard.py

Global discovery now rejects cross-sentence anchors individually before
acceptance. Valid siblings remain available and overall coverage is incomplete.
Unrelated programming errors still propagate.
"""
import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_claim_coverage as coverage  # noqa: E402
import server                               # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


DRAFT = (
    "An equal-tailed interval uses the 2.5th and 97.5th percentiles, i.e. "
    "it cuts 2.5% from each tail. The highest density interval contains "
    "the most probable values."
)
# Verbatim and unique in DRAFT. The splitter used to end a sentence after
# "i.e.", which put this anchor across a boundary; it now resolves.
ABBREVIATION_ANCHOR = "97.5th percentiles, i.e. it cuts 2.5% from each tail"
# Quoting across a real full stop still cannot resolve to one sentence.
CROSSING_ANCHOR = "from each tail. The highest density interval"


def assessor_for(anchor):
    def assessor(*, prompt, schema):
        if (schema == coverage.claim_discovery_output_schema()
                and "ANSWER DRAFT" in prompt):
            return {"discovered_claims": [{
                "type": "definition",
                "concept": "equal-tailed interval",
                "statement": "An equal-tailed interval cuts 2.5% from each tail.",
                "parameterisation": None,
                "source_anchor": anchor,
            }]}
        if schema == coverage.claim_discovery_output_schema():
            return {"discovered_claims": []}          # sentence audit
        if schema == coverage.claim_decomposition_output_schema():
            return {"requires_decomposition": False, "atomic_claims": []}
        if schema == coverage.claim_representation_output_schema():
            return {"represented": True, "represented_by": None}
        raise AssertionError("Unexpected schema.")
    return assessor


# 1. Item-level placement validation --------------------------------
print("\n[1] the pipeline quarantines an anchor outside one sentence")
spans = coverage.answer_sentence_spans(DRAFT)
check(len(spans) == 2,
      "the splitter no longer breaks after 'i.e.' (2 spans for 2 sentences)")
check(DRAFT.count(ABBREVIATION_ANCHOR) == 1, "abbreviation anchor is verbatim and unique")
completed = coverage.assess_claim_coverage_two_stage(
    answer_draft=DRAFT, existing_claims=[],
    assessor=assessor_for(ABBREVIATION_ANCHOR))
check(completed.discovered_claims[0].source_anchor == ABBREVIATION_ANCHOR,
      "an anchor quoted across 'i.e.' now completes coverage")
for name, anchor in (("crossing", CROSSING_ANCHOR),):
    check(DRAFT.count(anchor) == 1, f"{name} anchor is verbatim and unique")
    partial = coverage.assess_claim_coverage_two_stage(
        answer_draft=DRAFT, existing_claims=[], assessor=assessor_for(anchor))
    check(not partial.discovered_claims and len(partial.rejected_global_items) == 1,
          f"{name} anchor is rejected individually")
    check("does not resolve to one sentence" in partial.rejected_global_items[0].reason,
          f"{name} placement reason is preserved")


# 2. The server wrapper ---------------------------------------------------
print("\n[2] the server wrapper reports coverage as unavailable")


def wrapper_with(anchor):
    original = server.academic_claim_assessor.generate_claim_assessor_output
    fake = assessor_for(anchor)
    server.academic_claim_assessor.generate_claim_assessor_output = (
        lambda model, tokenizer, prompt, schema, max_tokens=None,
        diagnostic_raw_output=None:
        fake(prompt=prompt, schema=schema))
    try:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            result = server.assess_academic_claim_coverage(
                answer_draft=DRAFT, existing_claims=[])
        return result, err.getvalue()
    finally:
        server.academic_claim_assessor.generate_claim_assessor_output = original


for name, anchor in (("crossing", CROSSING_ANCHOR),):
    result, logged = wrapper_with(anchor)
    check(result.status == coverage.COVERAGE_STATUS_UNAVAILABLE
          and result.result is not None,
          f"{name}: status is coverage_assessment_unavailable")
    check(result.reasons == ["Local claim-coverage output could not be validated."],
          f"{name}: reader receives the existing generic validation wording")
    check("does not resolve to one sentence" in logged,
          f"{name}: the placement failure is kept in the server log")

# Well-placed anchors are untouched by the guard.
for name, anchor in (("plain", "cuts 2.5% from each tail"),
                     ("abbreviation", ABBREVIATION_ANCHOR)):
    result, logged = wrapper_with(anchor)
    check(result.status != coverage.COVERAGE_STATUS_UNAVAILABLE and not logged,
          f"{name}: an anchor inside one sentence completes normally")


# 3. Only that failure is absorbed ----------------------------------------
print("\n[3] any other ValueError in coverage still propagates")
original = server.academic_claim_coverage.assess_claim_coverage_two_stage


def unrelated(**kwargs):
    raise ValueError("an unrelated programming error")


server.academic_claim_coverage.assess_claim_coverage_two_stage = unrelated
try:
    server.assess_academic_claim_coverage(answer_draft=DRAFT, existing_claims=[])
    propagated = None
except ValueError as exc:
    propagated = exc
finally:
    server.academic_claim_coverage.assess_claim_coverage_two_stage = original
check(propagated is not None and "unrelated" in str(propagated),
      "an unrelated ValueError is not swallowed")


print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
