#!/usr/bin/env python3
"""
The check-further assessment reaches the Academic Chat response.

    python3 tests/test_academic_check_further_endpoint.py

Two things are checked at the endpoint: the assessment is computed from the
final (reconciled) attempt and added under "check_further" without disturbing
anything else in the payload; and if the assessment itself fails, the reader
still gets the answer, with the assessment replaced by an explicit statement
that it is unchecked rather than silently omitted.
"""
import asyncio
import contextlib
import io
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import reviewer_notes as rn  # noqa: E402
import server                # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


SECTION = ("Bayesian Decision Rules and Posterior Interpretation",
           "Are all 95% credible intervals the same?")


class Final:
    """A checked result with the attributes the rules read."""

    def __init__(self, broken=False):
        if broken:
            return          # nothing for the rules to read
        passage = rn.Passage(*SECTION, "t", 0.4)
        self.release = NS(safe_to_present=True, reasons=[],
                          status="release_allowed_with_unverified_claims")
        self.technical_claims = [NS(
            claim=NS(statement="For skewed posteriors the HDI is narrower."),
            verification=NS(status="not_technically_verified"),
            methodological_consistency=NS(
                status="methodological_consistency_not_established",
                passages=[passage], reasons=["r"]),
        )]
        self.discovered_claim_assessments = []
        self.references = []
        self.local_guidance = NS(passages=[passage])

    def to_dict(self):
        return {"answer_draft": "Synthetic answer.", "release": {"status": "x"}}


def run_with(final):
    def fake(model, tokenizer, question, **kwargs):
        return server.academic_reconciliation_orchestrator.AcademicReconciliationResult(
            initial=final, revised=None, revision_attempted=False)
    original = (server.ensure_model,
                server.academic_reconciliation_orchestrator.run_academic_reconciliation)
    server.ensure_model = lambda: None
    server.academic_reconciliation_orchestrator.run_academic_reconciliation = fake
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return asyncio.run(server.academic_chat_first_stage(
                {"question": "How do an ETI and an HDI differ?"}))
    finally:
        (server.ensure_model,
         server.academic_reconciliation_orchestrator.run_academic_reconciliation) = original


print("\n[1] a checked answer carries its check-further assessment")
payload = run_with(Final())
cf = payload.get("check_further", {})
check(payload.get("answer_draft") == "Synthetic answer.",
      "the existing payload is unchanged")
check(cf.get("level") == "check_advised",
      "an unsettled claim advises a check")
check(cf.get("groups") and cf["groups"][0]["heading"] == SECTION[1],
      "the claim is placed under the section it was judged against")
check(any(r["doi"] == "10.1080/00031305.1996.10474359"
          for r in cf["groups"][0]["references"]),
      "with that section's curated references")
check(len(cf.get("rules", [])) >= 7, "the rules travel with the assessment")

print("\n[2] a failure in the assessment does not cost the reader the answer")
payload = run_with(Final(broken=True))
cf = payload.get("check_further", {})
check(payload.get("answer_draft") == "Synthetic answer.",
      "the answer is still returned")
check(cf.get("level") == "check_needed" and "unchecked" in cf.get("headline", ""),
      "and the assessment says plainly that it is unchecked")
check(bool(cf.get("error")), "with the error recorded")

print()
if failures:
    print(f"{failures} check(s) failed.")
    sys.exit(1)
print("All check-further endpoint checks passed.")
