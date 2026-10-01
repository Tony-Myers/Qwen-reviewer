#!/usr/bin/env python3
"""
The evidence assessment reaches the Academic Chat response.

    python3 tests/test_academic_check_further_endpoint.py

Checked at the endpoint: the assessment is computed from the final
(reconciled) attempt and added under "check_further" without disturbing
anything else in the payload; and if the assessment itself fails, the reader
still gets the answer, told that the evidence check is incomplete -- never
that the answer is worth checking, which would be a claim about the answer
rather than about the checking.
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


print("\n[1] a checked answer carries its evidence assessment")
payload = run_with(Final())
cf = payload.get("check_further", {})
check(payload.get("answer_draft") == "Synthetic answer.",
      "the existing payload is unchanged")
check(cf.get("state") == "further_reading",
      "an unsettled point under a curated section offers further reading")
groups = cf.get("further_reading") or []
check(groups and groups[0]["heading"] == SECTION[1],
      "under the section it was judged against")
check(any(r["doi"] == "10.1080/00031305.1996.10474359" for r in groups[0]["references"]),
      "with that section's curated references")
check("diagnostics" in cf and "routing" in cf["diagnostics"],
      "the diagnostics travel with the assessment")

print("\n[2] a failure in the assessment does not cost the reader the answer")
payload = run_with(Final(broken=True))
cf = payload.get("check_further", {})
check(payload.get("answer_draft") == "Synthetic answer.",
      "the answer is still returned")
check(cf.get("state") == "incomplete" and cf.get("title") == "Evidence check incomplete",
      "the reader is told the evidence check is incomplete")
check(cf.get("worth_checking") == [],
      "and is not told the answer is worth checking")
check(bool(cf.get("diagnostics", {}).get("error")),
      "with the error recorded in the diagnostics only")

print()
if failures:
    print(f"{failures} check(s) failed.")
    sys.exit(1)
print("All check-further endpoint checks passed.")
