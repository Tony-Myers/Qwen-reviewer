#!/usr/bin/env python3
"""
One application-owned decision says whether the reader sees the answer.

    python3 tests/test_academic_presentation_policy.py

The server exposes presentation.mode -- release, qualified or withheld -- with
the release status that decided it as presentation.reason, and the page
renders that decision. Previously the page derived its own: it withheld any
answer not safe to present, except that it always showed one whose checking
was incomplete. That exception was meant for a first answer, but it also
showed a revision whose checking was incomplete, after a blocking problem had
been established in the original -- including a revision repeating the very
formula that had withheld it.

The rules:

  - no revision: safe to present -> release; checking incomplete -> qualified
    (a deliberate product decision); any other block -> withheld;
  - revision: safe to present -> release; anything else -> withheld; a
    revision is never qualified.

Run through the real /api/chat/academic endpoint, orchestration, release,
reconciliation and evidence check, and the page's own sendAcademicMessage
under Node. Only the model, the bibliographic and source services, the draft
generator and the reviser are replaced.
"""
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi.testclient import TestClient     # noqa: E402

import academic_chat                          # noqa: E402
import academic_check_further as cf           # noqa: E402
import academic_claim_assessor                # noqa: E402
import academic_claim_coverage as coverage    # noqa: E402
import academic_claims                        # noqa: E402
import academic_methodology as am             # noqa: E402
import academic_orchestrator as orchestrator  # noqa: E402
import academic_reconciliation as reconciliation  # noqa: E402
import academic_reconciliation_orchestrator as lifecycle  # noqa: E402
import academic_tools                         # noqa: E402
import server                                 # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


RELEASE, QUALIFIED, WITHHELD = "release", "qualified", "withheld"

# ---------------------------------------------------------------------------
# Drafts: the multiple-imputation relative-efficiency formula is the one
# technical claim the deterministic verifier recognises.
# ---------------------------------------------------------------------------
DOI = "10.1002/9780470316696"
MI_PARAMETERS = ("lambda is the fraction of missing information; "
                 "M is the number of imputations")
WRONG = academic_chat.TechnicalClaim(
    "formula", "multiple imputation relative efficiency",
    "RE = 1 + lambda/M", MI_PARAMETERS)
RIGHT = academic_chat.TechnicalClaim(
    "formula", "multiple imputation relative efficiency",
    "RE = 1 / (1 + lambda/M)", MI_PARAMETERS)
OTHER = academic_chat.TechnicalClaim(
    "interpretation", "number of imputations",
    "More imputations are needed when the fraction of missing information is high.",
    None)
WRONG_ANSWER = "The relative efficiency is RE = 1 + lambda/M."
RIGHT_ANSWER = "The relative efficiency is RE = 1 / (1 + lambda/M)."
OTHER_ANSWER = OTHER.statement
SOURCE_CLAIM = ("Five imputations are often sufficient when the fraction of "
                "missing information is moderate.")
SOURCE_TEXT = ("In practice five imputations are often sufficient when the "
               "fraction of missing information is moderate. ") * 3
SOURCE_ANSWER = "Rubin reported that five imputations are often sufficient."
REFERENCE = academic_chat.AcademicReference(
    "Multiple Imputation for Nonresponse in Surveys", "Rubin, D. B.", 1987,
    "Wiley", DOI)


def draft(answer, technical=(), references=(), source_claims=()):
    return academic_chat.AcademicDraft(
        answer_draft=answer, references=list(references),
        source_claims=[academic_chat.SourceClaim(c, i) for c, i in source_claims],
        technical_claims=list(technical))


SOURCED = dict(references=[REFERENCE], source_claims=[(SOURCE_CLAIM, 0)])

CANDIDATE = academic_tools.ReferenceCandidate(
    title=REFERENCE.title, authors=["Donald B. Rubin"], year=1987, venue="",
    doi=DOI, work_type="monograph")
orchestrator.verify_academic_reference = lambda **kwargs: (
    academic_tools.AcademicReferenceResult(
        crossref_verification=academic_tools.VerificationResult(
            status="verified", candidate=CANDIDATE, reasons=["Synthetic."]),
        doi_corroboration=None, related_corroboration=None,
        identity_conflict=False, reasons=["Synthetic."]))
orchestrator.resolve_retrieval_identity = lambda verification: (
    orchestrator.RetrievalIdentity(status="eligible", doi=DOI, reasons=["Synthetic."]))
server.discover_academic_source = lambda doi: academic_claims.SourceLocation(
    status="location_found", doi=doi, source="openalex", landing_page_url=None,
    pdf_url="https://journal.example/source.pdf", is_oa=True, reasons=["Synthetic."])

case = {}
revisions = []


def retrieve(location):
    if revisions and case.get("unretrievable"):
        return academic_claims.RetrievedSource(
            status="not_retrieved", doi=DOI, source="openalex", text=None,
            locator=None, reasons=["PDF source download failed."])
    return academic_claims.RetrievedSource(
        status="retrieved", doi=DOI, source="openalex", text=SOURCE_TEXT,
        locator="source.pdf", reasons=["Synthetic."])


def model_output(model, tokenizer, prompt, schema, *, max_tokens=512,
                 diagnostic_raw_output=None):
    if schema == coverage.claim_discovery_output_schema():
        failing = case.get("revised_coverage_fails") if revisions else case.get("coverage_fails")
        if failing:
            raise academic_claim_assessor.ClaimAssessorOutputError(
                "Claim assessor did not return valid JSON.")
        if "ANSWER DRAFT" in prompt and "RE = 1 + lambda/M" in prompt:
            # Coverage finds the formula wherever the answer states it.
            return {"discovered_claims": [{
                "type": "formula", "concept": "multiple imputation relative efficiency",
                "statement": "RE = 1 + lambda/M", "parameterisation": MI_PARAMETERS,
                "source_anchor": "RE = 1 + lambda/M"}]}
        return {"discovered_claims": []}
    if schema == coverage.claim_decomposition_output_schema():
        return {"requires_decomposition": False, "atomic_claims": []}
    if schema == coverage.claim_representation_output_schema():
        return {"represented": False, "represented_by": None}
    if schema == coverage.material_restriction_output_schema():
        return {"material_restriction_omitted": False}
    if schema == am.methodological_consistency_output_schema():
        return {"claim_proposition": "Synthetic claim proposition.",
                "guidance_proposition": "Synthetic guidance proposition.",
                "relationship": {
                    "methodologically_consistent": "supports",
                    "methodological_conflict": "incompatible",
                    "methodological_consistency_not_established": "insufficient",
                }[case.get("methodology", am.METHODOLOGICAL_STATUS_CONSISTENT)],
                "reason": "Synthetic."}
    if schema == academic_claims.claim_assessment_output_schema():
        status = case["recheck"] if revisions else case.get("source", "claim_supported")
        return {"status": status, "reason": "Synthetic."}
    raise AssertionError("unexpected schema")


def revise(model, tokenizer, original, corrections):
    revisions.append(corrections)
    return case["revision"]


server.retrieve_academic_source = retrieve
server.academic_claim_assessor.generate_claim_assessor_output = model_output
reconciliation.revise_academic_draft = revise
server.ensure_model = lambda: None
server.model = object()
server.tokenizer = object()
academic_chat.generate_academic_draft = lambda *args, **kwargs: case["original"]
client = TestClient(server.app, raise_server_exceptions=False)


def ask(**settings):
    case.clear()
    case.update(settings)
    revisions.clear()
    with contextlib.redirect_stderr(io.StringIO()):
        response = client.post(
            "/api/chat/academic",
            json={"question": "How many imputations are needed for multiple imputation?"})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# The page's own sendAcademicMessage, run under Node with a minimal DOM.
# ---------------------------------------------------------------------------
HTML = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")
NODE = shutil.which("node")
PAGE_FUNCTIONS = re.findall(r"^function \w+\(.*?\n}\n", HTML, re.S | re.M)
SEND = re.search(r"^async function sendAcademicMessage\(.*?\n}\n", HTML, re.S | re.M).group(0)
CONSTANTS = re.findall(r"^const ACADEMIC_\w+ =\n?.*?;\n", HTML, re.S | re.M)


def shown(payload):
    """The answer area the page renders for this response."""
    script = """
const element = () => ({innerHTML: '', style: {}, value: '', disabled: false,
                        textContent: '', focus() {}});
const ids = {};
const document = {getElementById: id => (ids[id] = ids[id] || element())};
const academicInput = element(); academicInput.value = 'q';
const academicSendBtn = element();
let academicGenerating = false;
const BASE = '';
const PAYLOAD = %s;
async function fetch() { return {ok: true, status: 200, json: async () => PAYLOAD}; }
class AcademicUserError extends Error {}
%s
%s
%s
sendAcademicMessage().then(() => process.stdout.write(ids['academicAnswer'].innerHTML));
""" % (json.dumps(payload), "\n".join(CONSTANTS), "\n".join(PAGE_FUNCTIONS), SEND)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    run = subprocess.run([NODE, f.name], capture_output=True, text=True, timeout=30)
    Path(f.name).unlink()
    if run.returncode != 0:
        print(run.stderr)
    return run.stdout


def displays(payload):
    return bool(payload.get("answer_draft")) and payload["answer_draft"] in shown(payload)


def expect(body, label, *, mode, reason, displayed, revised, evidence=None):
    presentation = body.get("presentation") or {}
    check(presentation.get("mode") == mode and presentation.get("reason") == reason,
          f"{label}: presentation {mode} ({reason})")
    check(body["reconciliation"]["revision_attempted"] is revised
          and len(revisions) == (1 if revised else 0),
          f"{label}: {'one revision' if revised else 'no revision'}")
    check(bool(body.get("answer_draft")),
          f"{label}: the answer stays in the payload")
    if evidence is not None:
        check(body["check_further"]["state"] == evidence,
              f"{label}: evidence check is {evidence}")
    if NODE:
        check(displays(body) is displayed,
              f"{label}: the page {'displays' if displayed else 'withholds'} the answer")


# ===========================================================================
print("\n[1] release_allowed")
body = ask(original=draft("Plain answer."))
expect(body, "release_allowed", mode=RELEASE, reason="release_allowed",
       displayed=True, revised=False)

print("\n[2] release_allowed_with_unverified_claims")
body = ask(original=draft(OTHER_ANSWER, [OTHER]))
expect(body, "unverified claims", mode=RELEASE,
       reason="release_allowed_with_unverified_claims", displayed=True, revised=False)

print("\n[3] release_allowed_with_methodological_conflict")
body = ask(original=draft(OTHER_ANSWER, [OTHER]),
           methodology=am.METHODOLOGICAL_STATUS_CONFLICT)
expect(body, "methodological conflict", mode=RELEASE,
       reason=orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
       displayed=True, revised=False, evidence=cf.STATE_WORTH_CHECKING)

print("\n[4] first-attempt checking_incomplete")
body = ask(original=draft(OTHER_ANSWER, [OTHER]), coverage_fails=True)
expect(body, "first-attempt incomplete", mode=QUALIFIED, reason="checking_incomplete",
       displayed=True, revised=False, evidence=cf.STATE_INCOMPLETE)
check(body["release"]["safe_to_present"] is False
      and body["check_further"]["summary"] == cf.INCOMPLETE_SUMMARY
      and "wrong" not in body["check_further"]["summary"],
      "first-attempt incomplete: release unchanged, and the reader is told checking was incomplete")

print("\n[5] first attempt: wrong formula only in prose, coverage unavailable")
body = ask(original=draft(WRONG_ANSWER), coverage_fails=True)
expect(body, "wrong formula unseen", mode=QUALIFIED, reason="checking_incomplete",
       displayed=True, revised=False, evidence=cf.STATE_INCOMPLETE)

print("\n[6] technical conflict -> corrected revision -> checking incomplete")
body = ask(original=draft(WRONG_ANSWER, [WRONG]),
           revision=draft(RIGHT_ANSWER, [RIGHT]), revised_coverage_fails=True)
expect(body, "corrected revision, incomplete", mode=WITHHELD, reason="checking_incomplete",
       displayed=False, revised=True)
check(body["reconciliation"]["initial"]["release"]["status"] == "blocked_technical_conflict"
      and body["release"]["status"] == "checking_incomplete"
      and body["release"]["safe_to_present"] is False
      and body["answer_draft"] == RIGHT_ANSWER,
      "corrected revision, incomplete: release unchanged; the revision stays in the payload")
if NODE:
    page = shown(body)
    check("A problem was found in the original answer" in page
          and "checking of it could not be completed" in page
          and "checking_incomplete" not in page,
          "corrected revision, incomplete: the reader is told why, without internal names")

print("\n[7] technical conflict -> revision keeps the wrong formula without its claim -> incomplete")
body = ask(original=draft(WRONG_ANSWER, [WRONG]),
           revision=draft(WRONG_ANSWER), revised_coverage_fails=True)
expect(body, "wrong formula kept, incomplete", mode=WITHHELD, reason="checking_incomplete",
       displayed=False, revised=True)

print("\n[8] the same wrong revision with coverage available")
body = ask(original=draft(WRONG_ANSWER, [WRONG]), revision=draft(WRONG_ANSWER))
expect(body, "wrong formula kept, coverage available", mode=WITHHELD,
       reason="blocked_technical_conflict", displayed=False, revised=True,
       evidence=cf.STATE_WORTH_CHECKING)

print("\n[9] blocked_technical_conflict")
body = ask(original=draft(WRONG_ANSWER, [WRONG]), revision=draft(WRONG_ANSWER, [WRONG]))
expect(body, "technical conflict", mode=WITHHELD, reason="blocked_technical_conflict",
       displayed=False, revised=True, evidence=cf.STATE_WORTH_CHECKING)

print("\n[10] blocked_source_contradiction")
body = ask(original=draft(SOURCE_ANSWER, **SOURCED), source="claim_contradicted",
           revision=draft(SOURCE_ANSWER, **SOURCED), recheck="claim_contradicted")
expect(body, "source contradiction", mode=WITHHELD, reason="blocked_source_contradiction",
       displayed=False, revised=True, evidence=cf.STATE_WORTH_CHECKING)

print("\n[11] blocked_unresolved_source_contradiction")
body = ask(original=draft(SOURCE_ANSWER, **SOURCED), source="claim_contradicted",
           revision=draft(SOURCE_ANSWER, **SOURCED), recheck="claim_supported",
           unretrievable=True)
expect(body, "unresolved contradiction", mode=WITHHELD,
       reason=lifecycle.RELEASE_STATUS_UNRESOLVED_SOURCE_CONTRADICTION,
       displayed=False, revised=True, evidence=cf.STATE_WORTH_CHECKING)
if NODE:
    check("could not be confirmed against that source" in shown(body),
          "unresolved contradiction: its own wording is unchanged")

print("\n[12] a corrected revision cleared for ordinary release")
body = ask(original=draft(WRONG_ANSWER, [WRONG]), revision=draft(RIGHT_ANSWER, [RIGHT]))
expect(body, "corrected revision", mode=RELEASE, reason="release_allowed",
       displayed=True, revised=True)

print("\n[13] no revision can be qualified")
statuses = ["release_allowed", "release_allowed_with_unverified_claims",
            orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT, "checking_incomplete",
            "blocked_technical_conflict", "blocked_source_contradiction",
            lifecycle.RELEASE_STATUS_UNRESOLVED_SOURCE_CONTRADICTION]
modes = {}
for status in statuses:
    for safe in (True, False):
        release = NS(status=status, safe_to_present=safe)
        modes[(status, safe, True)] = lifecycle.decide_presentation(release, revised=True).mode
        modes[(status, safe, False)] = lifecycle.decide_presentation(release, revised=False).mode
check(all(mode != QUALIFIED for (status, safe, revised), mode in modes.items() if revised),
      "a revision is never qualified, whatever its release")
check(all((mode == RELEASE) == safe for (status, safe, revised), mode in modes.items()),
      "release exactly when the final release is safe to present")
check([key for key, mode in modes.items() if mode == QUALIFIED]
      == [("checking_incomplete", False, False)],
      "qualified only for a first answer whose checking was incomplete")


# ===========================================================================
print("\n[UI] the page renders the decision and derives none of its own")
check("safe_to_present" not in SEND and "release?.status" not in SEND
      and "presentation.mode" in SEND,
      "sendAcademicMessage reads presentation.mode and not the release")
if NODE:
    def synthetic(mode, reason, status, safe):
        return {"answer_draft": "Synthetic answer text.",
                "release": {"status": status, "safe_to_present": safe, "reasons": []},
                "presentation": ({"mode": mode, "reason": reason} if mode else None)}

    check(not displays(synthetic(WITHHELD, "checking_incomplete", "checking_incomplete", False)),
          "a withheld revision with checking_incomplete cannot be displayed by a status exception")
    check(not displays(synthetic(WITHHELD, "release_allowed", "release_allowed", True)),
          "withheld is withheld even when the release would allow it")
    check(not displays(synthetic(None, None, "release_allowed", True)),
          "a response without a presentation decision is withheld")
    page = shown(synthetic(QUALIFIED, "checking_incomplete", "checking_incomplete", False))
    check("Synthetic answer text." in page and "Checking incomplete" in page,
          "qualified without an evidence check: the answer with the incomplete-checking note")

print()
if not NODE:
    print("SKIP: Node is not installed, so the page rendering checks did not run.")
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
