#!/usr/bin/env python3
"""
A revision clears a source contradiction only by a completed favourable re-check.

    python3 tests/test_academic_source_contradiction_reconciliation.py

When a source contradicts the first attempt, the answer is withheld and one
revision is made. The revision is assessed afresh, and until this change any
revision whose fresh assessment found no new contradiction was presented --
including when the source could not be re-checked at all, or when the
revision simply dropped the citation.

Now, for each source (normalised DOI) that contradicted the first attempt:

  - positively cleared: the revision still cites it and every revised claim
    citing it completed reassessment as supported or partially supported --
    the revision's own release stands;
  - still contradicted: the revision is contradicted again -- the existing
    blocked_source_contradiction stands;
  - resolution not established: anything else, including a dropped citation
    -- the revision is withheld as blocked_unresolved_source_contradiction.

Run through the real /api/chat/academic endpoint, orchestration, release,
reconciliation and evidence check. Only the model, the bibliographic and
source services, the draft generator and the reviser are replaced.
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


UNRESOLVED = "blocked_unresolved_source_contradiction"
CONTRADICTION = "blocked_source_contradiction"

# ---------------------------------------------------------------------------
# Two sources, each cited by one claim the first attempt makes.
# ---------------------------------------------------------------------------
DOI_A = "10.1002/9780470316696"
DOI_B = "10.1037/1082-989X.7.2.147"
CLAIM_A = ("Five imputations are often sufficient when the fraction of "
           "missing information is moderate.")
CLAIM_B = ("Listwise deletion is unbiased when data are missing completely "
           "at random.")
CHANGED_A = ("The number of imputations needed rises with the fraction of "
             "missing information.")
SENTENCE_1 = ("Multiple imputation with m imputations has relative efficiency "
              "approximately 1 / (1 + FMI/m).")
SENTENCE_A = ("Rubin showed that five imputations are often sufficient when "
              "the fraction of missing information is moderate.")
SENTENCE_B = ("Listwise deletion is unbiased when data are missing completely "
              "at random.")
SENTENCE_CHANGED = ("The number of imputations needed rises with the fraction "
                    "of missing information.")
PAGE_TEXT = {
    DOI_A: ("In practice five imputations are often sufficient when the "
            "fraction of missing information is moderate. The number of "
            "imputations needed rises with the fraction of missing "
            "information. ") * 3,
    DOI_B: ("Listwise deletion is unbiased when data are missing completely "
            "at random, although it discards information. ") * 3,
}
UNRELATED = "Posterior predictive checks compare replicated data with observed data. " * 10

REF_A = academic_chat.AcademicReference(
    title="Multiple Imputation for Nonresponse in Surveys",
    author="Rubin, D. B.", year=1987, venue="Wiley", doi=DOI_A)
REF_B = academic_chat.AcademicReference(
    title="Missing data: Our view of the state of the art",
    author="Schafer, J. L., & Graham, J. W.", year=2002,
    venue="Psychological Methods", doi=DOI_B)
REF_A_NO_DOI = academic_chat.AcademicReference(
    title=REF_A.title, author=REF_A.author, year=1987, venue="Wiley", doi=None)


def draft(answer, references, claims):
    return academic_chat.AcademicDraft(
        answer_draft=answer, references=references,
        source_claims=[academic_chat.SourceClaim(c, i) for c, i in claims],
        technical_claims=[])


ONE_SOURCE = draft(SENTENCE_1 + " " + SENTENCE_A, [REF_A], [(CLAIM_A, 0)])
TWO_SOURCES = draft(SENTENCE_1 + " " + SENTENCE_A + " " + SENTENCE_B,
                    [REF_A, REF_B], [(CLAIM_A, 0), (CLAIM_B, 1)])


def verify_reference(**kwargs):
    doi = kwargs.get("doi")
    if not doi:
        return academic_tools.AcademicReferenceResult(
            crossref_verification=academic_tools.VerificationResult(
                status="not_verified", candidate=None, reasons=["Synthetic."]),
            doi_corroboration=None, related_corroboration=None,
            identity_conflict=False, reasons=["Synthetic."])
    candidate = academic_tools.ReferenceCandidate(
        title=kwargs.get("title") or "", authors=["Synthetic Author"],
        year=kwargs.get("year"), venue="", doi=doi, work_type="journal-article")
    return academic_tools.AcademicReferenceResult(
        crossref_verification=academic_tools.VerificationResult(
            status="verified", candidate=candidate, reasons=["Synthetic."]),
        doi_corroboration=None, related_corroboration=None,
        identity_conflict=False, reasons=["Synthetic."])


def retrieval_identity(verification):
    crossref = verification.crossref_verification
    if crossref.status == "verified":
        return orchestrator.RetrievalIdentity(
            status="eligible", doi=crossref.candidate.doi, reasons=["Synthetic."])
    return orchestrator.RetrievalIdentity(
        status="not_eligible", doi=None, reasons=["Synthetic."])


# The current case: what each claim's assessment returns in each attempt, and
# which sources cannot be retrieved or contain other text on the re-check.
case = {}
revisions = []
revision_counts = []

SUPPORTED = {"status": "claim_supported", "reason": "Synthetic."}
PARTIAL = {"status": "claim_partially_supported", "reason": "Synthetic."}
NOT_SUPPORTED = {"status": "claim_not_supported", "reason": "Synthetic."}
CONTRADICTED = {"status": "claim_contradicted", "reason": "Synthetic."}
UNDECODABLE = academic_claim_assessor.ClaimAssessorOutputError(
    "Claim assessor did not return valid JSON.")


def model_output(model, tokenizer, prompt, schema, *, max_tokens=512):
    if schema == coverage.claim_discovery_output_schema():
        if case.get("coverage_fails") and revisions:
            raise academic_claim_assessor.ClaimAssessorOutputError(
                "Claim assessor did not return valid JSON.")
        return {"discovered_claims": []}
    if schema == coverage.claim_decomposition_output_schema():
        return {"requires_decomposition": False, "atomic_claims": []}
    if schema == coverage.claim_representation_output_schema():
        return {"represented": False, "represented_by": None}
    if schema == coverage.material_restriction_output_schema():
        return {"material_restriction_omitted": False}
    if schema == am.methodological_consistency_output_schema():
        return {"status": am.METHODOLOGICAL_STATUS_CONSISTENT, "reason": "Synthetic."}
    if schema == academic_claims.claim_assessment_output_schema():
        verdicts = case["recheck"] if revisions else case["initial"]
        claim = next(c for c in (CLAIM_A, CLAIM_B, CHANGED_A) if c in prompt)
        output = verdicts[claim]
        if isinstance(output, BaseException):
            raise output
        return output
    raise AssertionError("unexpected schema")


def retrieve(location):
    doi = location.doi
    if revisions and doi in case.get("unretrievable", ()):
        return academic_claims.RetrievedSource(
            status="not_retrieved", doi=doi, source="openalex", text=None,
            locator=None, reasons=["PDF source download failed."])
    text = UNRELATED if (revisions and doi in case.get("relocated", ())) else PAGE_TEXT[doi]
    pages = [academic_claims.ExtractedPage(page_number=1, text="Front matter. " * 10),
             academic_claims.ExtractedPage(page_number=4, text=text)]
    return academic_claims.RetrievedSource(
        status="retrieved", doi=doi, source="openalex",
        text="\n\n".join(p.text for p in pages), locator=f"{doi}.pdf",
        reasons=["Synthetic."], pages=pages)


def revise(model, tokenizer, original, corrections):
    revisions.append(corrections)
    return case["revision"]


server.ensure_model = lambda: None
server.model = object()
server.tokenizer = object()
academic_chat.generate_academic_draft = lambda *args, **kwargs: case["original"]
orchestrator.verify_academic_reference = verify_reference
orchestrator.resolve_retrieval_identity = retrieval_identity
server.discover_academic_source = lambda doi: academic_claims.SourceLocation(
    status="location_found", doi=doi, source="openalex", landing_page_url=None,
    pdf_url="https://journal.example/source.pdf", is_oa=True, reasons=["Synthetic."])
server.retrieve_academic_source = retrieve
server.academic_claim_assessor.generate_claim_assessor_output = model_output
reconciliation.revise_academic_draft = revise

client = TestClient(server.app, raise_server_exceptions=False)


def ask(*, revision, recheck, original=ONE_SOURCE, initial=None, **extra):
    case.clear()
    case.update(original=original, revision=revision, recheck=recheck,
                initial=initial or {CLAIM_A: CONTRADICTED, CLAIM_B: CONTRADICTED},
                **extra)
    revisions.clear()
    with contextlib.redirect_stderr(io.StringIO()):
        response = client.post("/api/chat/academic",
                               json={"question": "How many imputations are needed?"})
    assert response.status_code == 200, response.text
    revision_counts.append(len(revisions))
    return response.json()


def resolution(body):
    return body["reconciliation"].get("source_contradiction_resolution")


def outcomes(body):
    return {s["doi"]: s["outcome"] for s in resolution(body)["sources"]}


def common(body, label):
    """What every contradiction-triggered case must show."""
    initial = body["reconciliation"]["initial"]
    check(initial["release"]["status"] == CONTRADICTION
          and body["reconciliation"]["revision_attempted"] is True
          and len(revisions) == 1,
          f"{label}: the contradiction withheld the first attempt and one revision was made")
    check(body["answer_draft"] == case["revision"].answer_draft
          and body["reconciliation"]["revised"] is not None,
          f"{label}: the revised answer and its own assessment stay in the payload")


def cleared(body, label):
    common(body, label)
    own = body["reconciliation"]["revised"]["release"]
    check(resolution(body)["status"] == lifecycle.RESOLUTION_POSITIVELY_CLEARED
          and body["release"] == own and body["release"]["safe_to_present"] is True
          and body["presentation"]["mode"] == "release",
          f"{label}: positively cleared; the revision's own release stands "
          f"({body['release']['status']})")
    check(body["check_further"]["state"] != cf.STATE_WORTH_CHECKING,
          f"{label}: nothing worth checking is reported")


def unresolved(body, label, *, retry):
    common(body, label)
    own = body["reconciliation"]["revised"]["release"]
    check(resolution(body)["status"] == lifecycle.RESOLUTION_NOT_ESTABLISHED,
          f"{label}: resolution not established")
    check(body["release"]["status"] == UNRESOLVED
          and body["release"]["safe_to_present"] is False
          and body["presentation"] == {"mode": "withheld", "reason": UNRESOLVED},
          f"{label}: withheld as {UNRESOLVED}")
    check(own["status"] not in (UNRESOLVED, CONTRADICTION),
          f"{label}: the revision's own release is kept unaltered in the audit "
          f"({own['status']})")
    evidence = body["check_further"]
    check(evidence["state"] == cf.STATE_WORTH_CHECKING
          and evidence["summary"] == cf._BLOCKED_SUMMARIES[UNRESOLVED],
          f"{label}: the reader is told why it is withheld")
    check(evidence["secondary"] == (cf.RETRY_MAY_HELP if retry else ""),
          f"{label}: {'suggests' if retry else 'does not suggest'} trying again")
    reader = json.dumps({k: v for k, v in evidence.items() if k != "diagnostics"})
    check(UNRESOLVED not in reader and DOI_A not in reader and "Error" not in reader,
          f"{label}: no internal status, DOI or error at reader level")


# ===========================================================================
print("\n[1] re-checked and supported")
body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: SUPPORTED})
cleared(body, "supported")

print("\n[2] re-checked and partially supported")
body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: PARTIAL})
cleared(body, "partially supported")

print("\n[3] contradicted again")
body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: CONTRADICTED})
common(body, "contradicted again")
check(body["release"]["status"] == CONTRADICTION
      and body["release"] == body["reconciliation"]["revised"]["release"]
      and resolution(body)["status"] == lifecycle.RESOLUTION_STILL_CONTRADICTED,
      "contradicted again: the existing contradiction block stands, not the new state")

print("\n[4] re-checked and not supported")
unresolved(ask(revision=ONE_SOURCE, recheck={CLAIM_A: NOT_SUPPORTED}),
           "not supported", retry=False)

print("\n[5] source not retrieved on the re-check")
unresolved(ask(revision=ONE_SOURCE, recheck={CLAIM_A: SUPPORTED},
               unretrievable={DOI_A}), "not retrieved", retry=True)

print("\n[6] claim not located on the re-check")
unresolved(ask(revision=ONE_SOURCE, recheck={CLAIM_A: SUPPORTED},
               relocated={DOI_A}), "not located", retry=True)

print("\n[7] semantic assessment not completed on the re-check")
body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: UNDECODABLE})
unresolved(body, "assessment not completed", retry=True)
revised_claim = resolution(body)["sources"][0]["revised_claims"][0]
check(revised_claim["claim_assessment"] is None
      and revised_claim["claim_assessment_error"],
      "assessment not completed: the audit records the failed re-check")

print("\n[8] DOI removed from the citation")
body = ask(revision=draft(ONE_SOURCE.answer_draft, [REF_A_NO_DOI], [(CLAIM_A, 0)]),
           recheck={CLAIM_A: SUPPORTED})
unresolved(body, "DOI removed", retry=False)
check(resolution(body)["sources"][0]["revised_claims"] == [],
      "DOI removed: no revised claim is associated with the contradicted source")

print("\n[9] structured claim and its prose removed")
unresolved(ask(revision=draft(SENTENCE_1, [], []), recheck={}),
           "claim and prose removed", retry=False)

print("\n[10] structured claim removed, identical prose kept")
body = ask(revision=draft(ONE_SOURCE.answer_draft, [REF_A], []), recheck={})
unresolved(body, "structure removed, prose kept", retry=False)

print("\n[11] changed proposition, same DOI, completed supported re-check")
body = ask(revision=draft(SENTENCE_1 + " " + SENTENCE_CHANGED, [REF_A], [(CHANGED_A, 0)]),
           recheck={CHANGED_A: SUPPORTED})
cleared(body, "changed proposition")
check(resolution(body)["sources"][0]["revised_claims"][0]["claim"] == CHANGED_A,
      "changed proposition: the revised claim citing the source is the one assessed")

print("\n[12] two contradicted sources, both re-checked and supported")
body = ask(original=TWO_SOURCES, revision=TWO_SOURCES,
           recheck={CLAIM_A: SUPPORTED, CLAIM_B: PARTIAL})
cleared(body, "both supported")
check(outcomes(body) == {DOI_A.lower(): lifecycle.RESOLUTION_POSITIVELY_CLEARED,
                         DOI_B.lower(): lifecycle.RESOLUTION_POSITIVELY_CLEARED},
      "both supported: each source is cleared on its own")

print("\n[13] one source cleared, the other not retrieved")
body = ask(original=TWO_SOURCES, revision=TWO_SOURCES,
           recheck={CLAIM_A: SUPPORTED, CLAIM_B: SUPPORTED}, unretrievable={DOI_B})
unresolved(body, "one cleared, one not retrieved", retry=True)
check(outcomes(body) == {DOI_A.lower(): lifecycle.RESOLUTION_POSITIVELY_CLEARED,
                         DOI_B.lower(): lifecycle.RESOLUTION_NOT_ESTABLISHED},
      "one cleared, one not retrieved: the audit shows each source's outcome")

print("\n[13b] one source cleared, the other's citation dropped")
body = ask(original=TWO_SOURCES,
           revision=draft(SENTENCE_1 + " " + SENTENCE_A, [REF_A], [(CLAIM_A, 0)]),
           recheck={CLAIM_A: SUPPORTED})
unresolved(body, "one cleared, one dropped", retry=False)

print("\n[13c] revised coverage unavailable as well as an unretrieved source")
body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: SUPPORTED},
           unretrievable={DOI_A}, coverage_fails=True)
check(body["reconciliation"]["revised"]["release"]["status"] == "checking_incomplete"
      and body["release"]["status"] == UNRESOLVED
      and body["release"]["safe_to_present"] is False,
      "an incomplete revision is withheld as unresolved, not shown as checking_incomplete")

# ===========================================================================
print("\n[14] no second revision")
check(len(revision_counts) == 15 and set(revision_counts) == {1},
      f"each of the {len(revision_counts)} cases above made exactly one revision")

print("\n[15] the original contradiction and the revision stay inspectable")
body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: SUPPORTED}, unretrievable={DOI_A})
initial_claim = body["reconciliation"]["initial"]["source_claims"][0]
check(initial_claim["claim_assessment"]["status"] == "claim_contradicted"
      and initial_claim["claim_assessment"]["evidence"],
      "reconciliation.initial keeps the contradicted claim and its evidence")
source = resolution(body)["sources"][0]
check(source["doi"] == DOI_A.lower()
      and source["original_claims"][0]["claim"] == CLAIM_A
      and source["original_claims"][0]["evidence"]
      and all(e["page_number"] == 4 for e in source["original_claims"][0]["evidence"]),
      "the resolution audit keeps the DOI, the claim, and its passages with page provenance")
check(source["revised_claims"][0]["source_retrieval"] == "not_retrieved"
      and source["outcome"] == lifecycle.RESOLUTION_NOT_ESTABLISHED,
      "and the revised claim's re-check state and outcome")

# ===========================================================================
print("\n[controls] paths without a source contradiction are unchanged")
body = ask(revision=ONE_SOURCE, recheck={}, initial={CLAIM_A: SUPPORTED})
check(body["reconciliation"]["revision_attempted"] is False
      and "source_contradiction_resolution" not in body["reconciliation"]
      and body["release"] == body["reconciliation"]["initial"]["release"],
      "a supported first attempt: no revision, no resolution, release unchanged")

technical_initial = NS(release=NS(status="blocked_technical_conflict"), source_claims=[])
check(lifecycle.assess_source_contradiction_resolution(
          technical_initial, NS(release=NS(status="release_allowed"), source_claims=[]))
      is None,
      "a technical-conflict revision gets no source-contradiction resolution")
still_technical = lifecycle.AcademicReconciliationResult(
    initial=NS(), revised=NS(release=NS(status="blocked_technical_conflict")),
    revision_attempted=True,
    source_contradiction_resolution=lifecycle.SourceContradictionResolution(
        status=lifecycle.RESOLUTION_NOT_ESTABLISHED))
check(still_technical.unresolved_release is None,
      "a revision blocked on its own evidence keeps its own blocking release")

# ===========================================================================
print("\n[UI] what the reader and the technical details show")
html = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")
withheld = html[html.index("function academicWithheldMessage"):
                html.index("async function sendAcademicMessage")]
check("'blocked_unresolved_source_contradiction'" in withheld
      and "A revised answer was prepared, but it could not be confirmed against that" in withheld,
      "the answer area names the reason when an unconfirmed revision is withheld")
node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run.")
else:
    page_functions = re.findall(r"^function \w+\(.*?\n}\n", html, re.S | re.M)

    def render(expression):
        script = "\n".join(page_functions) + (
            f"\nprocess.stdout.write({expression});")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(script)
        run = subprocess.run([node, f.name], capture_output=True, text=True,
                             timeout=30)
        Path(f.name).unlink()
        if run.returncode != 0:
            print(run.stderr)
        return run.stdout

    body = ask(revision=ONE_SOURCE, recheck={CLAIM_A: UNDECODABLE})
    page = render("renderAcademicCheckFurther(" + json.dumps(body["check_further"]) + ", '', '')")
    reader = page.split('<details class="technical-details">')[0]
    check(cf._BLOCKED_SUMMARIES[UNRESOLVED] in reader and cf.RETRY_MAY_HELP in reader
          and UNRESOLVED not in reader and "Error" not in reader,
          "evidence check: the reason and the retry hint, nothing internal")
    audit = render("renderAcademicAudit(" + json.dumps(body) + ")")
    check("Source contradiction reconciliation" in audit
          and "Resolution not established" in audit
          and CLAIM_A in audit and "page 4" in audit
          and "assessment: not completed" in audit,
          "technical details: the original claim, its passages and the revised re-check")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
