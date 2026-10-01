#!/usr/bin/env python3
"""
A claim anchor that does not sit inside one answer sentence must not cost
the reader the answer.

    python3 tests/test_academic_coverage_sentence_guard.py

Background: claim discovery accepts any verbatim, unique anchor from the
answer, but decomposition then requires that anchor to lie inside one
application-owned sentence. When it does not -- the anchor crosses a full
stop, or the sentence splitter breaks inside it after an abbreviation such
as "i.e." -- resolve_claim_source_context raises ValueError. Nothing caught
it, so the Academic Chat endpoint answered with a bare 500. The splitter no
longer breaks after "i.e." and similar abbreviations (see
test_academic_sentence_spans.py), but a model can still quote across a real
full stop, so the guard remains.

Checked here:
  1. the pipeline behaviour itself, unchanged (documents the cause);
  2. the server's coverage wrapper turns it into "coverage unavailable",
     the pipeline's own designed failure state, which the release reports
     as checking incomplete;
  3. only that failure is absorbed: any other ValueError still propagates,
     as the endpoint tests require of programming errors.
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


# 1. The cause, in the unchanged pipeline --------------------------------
print("\n[1] the pipeline raises ValueError for an anchor outside one sentence")
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
    try:
        coverage.assess_claim_coverage_two_stage(
            answer_draft=DRAFT, existing_claims=[],
            assessor=assessor_for(anchor))
        raised = None
    except Exception as exc:                                    # noqa: BLE001
        raised = exc
    check(type(raised) is ValueError
          and "does not resolve to one sentence" in str(raised),
          f"{name} anchor raises a plain ValueError (not ClaimCoverageOutputError)")


# 2. The server wrapper ---------------------------------------------------
print("\n[2] the server wrapper reports coverage as unavailable")


def wrapper_with(anchor):
    original = server.academic_claim_assessor.generate_claim_assessor_output
    fake = assessor_for(anchor)
    server.academic_claim_assessor.generate_claim_assessor_output = (
        lambda model, tokenizer, prompt, schema, max_tokens=None:
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
          and result.result is None,
          f"{name}: status is coverage_assessment_unavailable")
    check(any("single answer sentence" in r for r in result.reasons),
          f"{name}: the reason names the sentence problem")
    check("does not resolve to one sentence" in logged,
          f"{name}: the traceback is kept in the server log")

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
