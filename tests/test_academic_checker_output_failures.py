#!/usr/bin/env python3
"""
Unusable checker output must not destroy an answer, nor stand as a finding.

    python3 tests/test_academic_checker_output_failures.py

Two checking models could return output the application cannot use and, until
this change, turned a fully generated answer into an HTTP 500:

  A. the dropped-condition (material-restriction) check on each occurrence of
     a discovered claim;
  B. the semantic assessment of a source claim whose passages were located in
     a retrieved source.

Each is run through the real /api/chat/academic endpoint, orchestrator,
release, reconciliation and evidence check, with the real reviewer notes.
Only the model, the bibliographic and source services and the draft
generator are replaced. Checked, for each unusable output:

  - HTTP 200 and the answer is returned;
  - the failure is recorded as "not completed" and never as a finding
    (a restriction is null, never false; a source assessment is null, never a
    support status);
  - release and revision are what they would be without that check;
  - the remaining checks still run;
  - the evidence check is incomplete, and the error stays technical.

Valid outputs are unchanged controls, a genuine contradiction still withholds
the answer and triggers a revision, and input errors, programming errors and
backend failures still propagate as before.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi.testclient import TestClient     # noqa: E402

import academic_chat                          # noqa: E402
from methodology_fixtures import methodology_output
import academic_check_further as cf           # noqa: E402
import academic_claim_assessor                # noqa: E402
import academic_claim_coverage as coverage    # noqa: E402
import academic_claims                        # noqa: E402
import academic_methodology as am             # noqa: E402
import academic_orchestrator as orchestrator  # noqa: E402
import academic_reconciliation as reconciliation  # noqa: E402
import academic_tools                         # noqa: E402
import server                                 # noqa: E402
from llm_backend import BackendError          # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


# ---------------------------------------------------------------------------
# A checked answer with one source claim and two discovered claims.
# ---------------------------------------------------------------------------
QUESTION = "How many imputations are needed for multiple imputation?"
DOI = "10.1002/9780470316696"
SENTENCE_1 = ("Multiple imputation with m imputations has relative efficiency "
              "approximately 1 / (1 + FMI/m).")
SENTENCE_2 = ("Rubin showed that five imputations are often sufficient when the "
              "fraction of missing information is moderate.")
ANSWER = SENTENCE_1 + " " + SENTENCE_2
CLAIM_1 = "Relative efficiency is approximately 1 / (1 + FMI/m)."
CLAIM_2 = "Five imputations are often sufficient."
SOURCE_CLAIM = ("Five imputations are often sufficient when the fraction of "
                "missing information is moderate.")
SOURCE_TEXT = (("Chapter 4. " * 5 + "In practice five imputations are often "
                "sufficient when the fraction of missing information is "
                "moderate, because relative efficiency is already high. ") * 3)


def generate_draft(*args, **kwargs):
    return academic_chat.AcademicDraft(
        answer_draft=ANSWER,
        references=[academic_chat.AcademicReference(
            title="Multiple Imputation for Nonresponse in Surveys",
            author="Rubin, D. B.", year=1987, venue="Wiley", doi=DOI)],
        source_claims=[academic_chat.SourceClaim(claim=SOURCE_CLAIM,
                                                 reference_index=0)],
        technical_claims=[])


CANDIDATE = academic_tools.ReferenceCandidate(
    title="Multiple Imputation for Nonresponse in Surveys",
    authors=["Donald B. Rubin"], year=1987, venue="", doi=DOI,
    work_type="monograph")


def verify_reference(**kwargs):
    return academic_tools.AcademicReferenceResult(
        crossref_verification=academic_tools.VerificationResult(
            status="verified", candidate=CANDIDATE, reasons=["Synthetic."]),
        doi_corroboration=None, related_corroboration=None,
        identity_conflict=False, reasons=["Synthetic."])


VALID_FALSE = {"material_restriction_omitted": False}
VALID_TRUE = {"material_restriction_omitted": True}
SUPPORTED = {"status": "claim_supported", "reason": "Synthetic."}
NOT_SUPPORTED = {"status": "claim_not_supported", "reason": "Synthetic."}
CONTRADICTED = {"status": "claim_contradicted", "reason": "Synthetic."}
UNDECODABLE = academic_claim_assessor.ClaimAssessorOutputError(
    "Claim assessor did not return valid JSON.")

# What the model returns in the current case: the first occurrence's
# restriction check, the source assessment, and whether the standalone judge
# finds the first claim in conflict with the guidance.
case = {}


def model_output(model, tokenizer, prompt, schema, *, max_tokens=512,
                 diagnostic_raw_output=None):
    if schema == coverage.claim_discovery_output_schema():
        if "ANSWER DRAFT" not in prompt:
            return {"discovered_claims": []}
        return {"discovered_claims": [
            {"type": "formula", "concept": "relative efficiency",
             "statement": CLAIM_1, "parameterisation": None,
             "source_anchor": "relative efficiency approximately 1 / (1 + FMI/m)"},
            {"type": "interpretation", "concept": "number of imputations",
             "statement": CLAIM_2, "parameterisation": None,
             "source_anchor": ("five imputations are often sufficient when the "
                               "fraction of missing information is moderate")},
        ]}
    if schema == coverage.claim_decomposition_output_schema():
        return {"requires_decomposition": False, "atomic_claims": []}
    if schema == coverage.claim_representation_output_schema():
        return {"represented": False, "represented_by": None}
    if schema == coverage.material_restriction_output_schema():
        # The second occurrence always loses a condition, so its contextual
        # check runs and shows that checking continued past the first.
        output = case["restriction"] if CLAIM_1 in prompt else VALID_TRUE
    elif schema in (am.methodological_coexistence_output_schema(),
                  am.methodological_establishment_output_schema()):
        standalone = "VERIFIED SOURCE SENTENCE" not in prompt
        output = (
            methodology_output(schema, 'methodological_conflict', "Synthetic.")
            if case.get("standalone_conflict") and standalone and CLAIM_1 in prompt
            else methodology_output(schema, 'methodologically_consistent', "Synthetic."))
    elif schema == academic_claims.claim_assessment_output_schema():
        output = case["source"]
    else:
        raise AssertionError("unexpected schema")
    if isinstance(output, BaseException):
        raise output
    return output


revisions = []


def revise(model, tokenizer, draft, corrections):
    revisions.append(corrections)
    return draft


server.ensure_model = lambda: None
server.model = object()
server.tokenizer = object()
academic_chat.generate_academic_draft = generate_draft
orchestrator.verify_academic_reference = verify_reference
orchestrator.resolve_retrieval_identity = lambda verification: (
    orchestrator.RetrievalIdentity(status="eligible", doi=DOI,
                                   reasons=["Synthetic."]))
server.discover_academic_source = lambda doi: academic_claims.SourceLocation(
    status="location_found", doi=doi, source="openalex",
    landing_page_url=None, pdf_url="https://journal.example/source.pdf",
    is_oa=True, reasons=["Synthetic."])
server.retrieve_academic_source = lambda location: academic_claims.RetrievedSource(
    status="retrieved", doi=DOI, source="openalex", text=SOURCE_TEXT,
    locator="source.pdf", reasons=["Synthetic."])
server.academic_claim_assessor.generate_claim_assessor_output = model_output
reconciliation.revise_academic_draft = revise
original_locator = academic_claims.prepare_claim_support

client = TestClient(server.app, raise_server_exceptions=False)
strict_client = TestClient(server.app, raise_server_exceptions=True)


def ask(restriction=VALID_FALSE, source=SUPPORTED, standalone_conflict=False):
    case.update(restriction=restriction, source=source,
                standalone_conflict=standalone_conflict)
    revisions.clear()
    with contextlib.redirect_stderr(io.StringIO()):
        response = client.post("/api/chat/academic", json={"question": QUESTION})
    try:
        body = response.json()
    except ValueError:
        body = None
    return response.status_code, body


def raised_by(restriction=VALID_FALSE, source=SUPPORTED):
    """The exception the endpoint lets through, if any."""
    case.update(restriction=restriction, source=source, standalone_conflict=False)
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            strict_client.post("/api/chat/academic", json={"question": QUESTION})
    except Exception as exc:                                  # noqa: BLE001
        return exc
    return None


def reader_view(body):
    return json.dumps({k: v for k, v in body["check_further"].items()
                       if k != "diagnostics"})


def occurrence(body, claim):
    return next(item for item in body["claim_context_assessments"]
                if item["claim_statement"] == claim)


def methodology_ran(body):
    return (len(body["technical_claims"]) == 2
            and all(item["methodological_consistency"] is not None
                    for item in body["technical_claims"]))


# ===========================================================================
print("\n[A0] dropped-condition controls")
status, control = ask(restriction=VALID_FALSE)
check(status == 200 and control["answer_draft"] == ANSWER,
      "valid False: HTTP 200 and the answer")
first = occurrence(control, CLAIM_1)
check(first["material_restriction_omitted"] is False
      and "material_restriction_assessment_error" not in first
      and first["contextual_methodological_consistency"] is None,
      "valid False: no omission, no error, no contextual check")
check(control["check_further"]["state"] != cf.STATE_INCOMPLETE,
      f"valid False: the evidence check is complete ({control['check_further']['state']})")
CONTROL_RELEASE = control["release"]["status"]

status, body = ask(restriction=VALID_TRUE)
first = occurrence(body, CLAIM_1)
check(status == 200 and first["material_restriction_omitted"] is True
      and first["contextual_methodological_consistency"] is not None,
      "valid True: omission found and the contextual check runs")

status, body = ask(restriction=VALID_TRUE, standalone_conflict=True)
check(body["release"]["status"] == "release_allowed_with_unverified_claims",
      "valid True with a standalone conflict: the contextual check supersedes it")


# ===========================================================================
for label, output in (
    ('the string "true"', {"material_restriction_omitted": "true"}),
    ("an extra field", {"material_restriction_omitted": True, "reason": "x"}),
    ("undecodable output", UNDECODABLE),
):
    print(f"\n[A] dropped-condition output: {label}")
    status, body = ask(restriction=output)
    check(status == 200 and body is not None and body["answer_draft"] == ANSWER,
          "HTTP 200 and the answer is returned")
    if status != 200 or body is None:
        continue
    first = occurrence(body, CLAIM_1)
    check(first["material_restriction_omitted"] is None,
          "the restriction is recorded as null, never false")
    check(bool(first.get("material_restriction_assessment_error")),
          "its assessment_error is kept in the technical payload")
    check(first["contextual_methodological_consistency"] is None,
          "the contextual check is skipped for that occurrence")
    check(occurrence(body, CLAIM_2)["contextual_methodological_consistency"] is not None,
          "the next occurrence is still checked in context")
    check(methodology_ran(body),
          "technical and methodological checking still run for every claim")
    check(body["release"]["status"] == CONTROL_RELEASE
          and body["release"]["safe_to_present"] is True,
          f"release is unchanged and presentable ({body['release']['status']})")
    check(body["reconciliation"]["revision_attempted"] is False and not revisions,
          "no revision")
    check(body["check_further"]["state"] == cf.STATE_INCOMPLETE
          and body["check_further"]["summary"] == cf.INCOMPLETE_SUMMARY,
          "the evidence check is incomplete")
    diagnostics = body["check_further"]["diagnostics"]
    check(diagnostics["counts"]["failed_restriction_checks"] == 1
          and diagnostics["failed_restriction_checks"][0]["answer_sentence"] == SENTENCE_1
          and diagnostics["lost_conditions"][0]["answer_sentence"] == SENTENCE_2
          and len(diagnostics["lost_conditions"]) == 1,
          "diagnostics: one failed context check, not counted as a lost condition")
    check("Error" not in reader_view(body),
          "no error text reaches the reader")

print("\n[A] a failed context check does not supersede a standalone conflict")
status, body = ask(restriction=UNDECODABLE, standalone_conflict=True)
answered = status == 200 and body is not None
check(answered
      and body["release"]["status"] == orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT
      and body["release"]["safe_to_present"] is True,
      "the standalone conflict stands, and stays advisory")
check(answered and body["reconciliation"]["revision_attempted"] is False,
      "no revision")
check(answered and body["check_further"]["state"] == cf.STATE_WORTH_CHECKING
      and body["check_further"]["secondary"] == cf.INCOMPLETE_WITH_CONCERN_SECONDARY,
      "worth checking stays primary, with the incomplete secondary")

print("\n[A] other failures still propagate")
for label, exc in (
    ("TypeError", TypeError("synthetic programming error")),
    ("plain ValueError", ValueError("synthetic unexpected error")),
):
    raised = raised_by(restriction=exc)
    check(type(raised) is type(exc), f"{label} is not swallowed")
status, body = ask(restriction=BackendError("No llama-server is listening."))
check(status == 502 and body["error"] == "Academic Chat local model unavailable.",
      "a backend failure still returns 502")


# ===========================================================================
print("\n[B0] source-assessment controls")
status, supported = ask(source=SUPPORTED)
item = supported["source_claims"][0]
check(status == 200 and item["claim_assessment"]["status"] == "claim_supported"
      and "claim_assessment_error" not in item,
      "supported: assessed, no error")
check(supported["check_further"]["state"] != cf.STATE_INCOMPLETE,
      "supported: the evidence check is complete")
SOURCE_CONTROL_RELEASE = supported["release"]["status"]

status, body = ask(source=NOT_SUPPORTED)
check(status == 200
      and body["source_claims"][0]["claim_assessment"]["status"] == "claim_not_supported"
      and body["release"]["status"] == SOURCE_CONTROL_RELEASE,
      "not supported: assessed, release as before")

status, body = ask(source=CONTRADICTED)
check(status == 200 and body["release"]["status"] == "blocked_source_contradiction"
      and body["release"]["safe_to_present"] is False,
      "contradicted: release is still blocked")
check(body["reconciliation"]["revision_attempted"] is True and len(revisions) == 1
      and revisions[0].source,
      "contradicted: the existing revision path still runs with the contradiction")


for label, output in (
    ("an invalid status", {"status": "claim_probably_supported", "reason": "x"}),
    ("an empty reason", {"status": "claim_supported", "reason": " "}),
    ("undecodable output", UNDECODABLE),
):
    print(f"\n[B] source-assessment output: {label}")
    status, body = ask(source=output)
    check(status == 200 and body is not None and body["answer_draft"] == ANSWER,
          "HTTP 200 and the answer is returned")
    if status != 200 or body is None:
        continue
    item = body["source_claims"][0]
    check(item["claim_assessment"] is None,
          "claim_assessment is null: no support status is implied")
    check(bool(item.get("claim_assessment_error")),
          "claim_assessment_error is kept in the technical payload")
    check(item["claim_location"]["status"] == "claim_located"
          and len(item["claim_location"]["evidence"]) > 0
          and item["reference"]["proposed_reference"]["doi"] == DOI
          and item["retrieval_identity"]["doi"] == DOI,
          "the located evidence and the reference identity are kept")
    check(body["release"]["status"] == SOURCE_CONTROL_RELEASE
          and body["release"]["status"] != "blocked_source_contradiction"
          and body["release"]["safe_to_present"] is True,
          f"release is neither blocked nor changed ({body['release']['status']})")
    check(body["reconciliation"]["revision_attempted"] is False and not revisions,
          "no revision")
    check(body["claim_coverage"]["status"] == coverage.COVERAGE_STATUS_MISSING_FOUND
          and len(body["claim_context_assessments"]) == 2 and methodology_ran(body),
          "coverage, context and methodology checking still run")
    check(body["check_further"]["state"] == cf.STATE_INCOMPLETE
          and body["check_further"]["secondary"]
          == cf.INCOMPLETE_SECONDARY + " " + cf.SOURCE_INCOMPLETE_NOTE,
          "the evidence check is incomplete, saying a source could not be fully checked")
    diagnostics = body["check_further"]["diagnostics"]
    check(diagnostics["counts"]["failed_source_assessments"] == 1
          and diagnostics["failed_source_assessments"][0]["located_passages"] > 0
          and diagnostics["failed_source_assessments"][0]["assessment_error"],
          "diagnostics record the failed source assessment and its evidence")
    check("Error" not in reader_view(body),
          "no error text reaches the reader")

print("\n[B] other failures still propagate")
raised = raised_by(source=TypeError("synthetic programming error"))
check(type(raised) is TypeError, "TypeError is not swallowed")
academic_claims.prepare_claim_support = lambda retrieved, claim: (
    academic_claims.ClaimSupportResult(
        status="claim_located", source_status="retrieved",
        claim_status="located", doi=DOI, evidence=[], reasons=["Synthetic."]))
try:
    raised = raised_by(source=SUPPORTED)
finally:
    academic_claims.prepare_claim_support = original_locator
check(type(raised) is ValueError
      and not isinstance(raised, academic_claims.ClaimAssessmentOutputError),
      f"an input ValueError (no located evidence) is not swallowed ({raised!r})")
status, body = ask(source=BackendError("No llama-server is listening."))
check(status == 502 and body["error"] == "Academic Chat local model unavailable.",
      "a backend failure still returns 502")


# ===========================================================================
print("\n[UI] technical cards and the reader's evidence check")
node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run.")
else:
    html = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")
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

    status, failed_context = ask(restriction=UNDECODABLE)
    status_source, failed_source = ask(source=UNDECODABLE)
    if failed_context is None or failed_source is None or status != 200 or status_source != 200:
        check(False, "the failure cases must be answered before their rendering can be checked")
        print()
        print(f"{failures} check(s) FAILED.")
        sys.exit(1)
    card = render("renderAcademicClaimContext("
                  + json.dumps(occurrence(failed_context, CLAIM_1)) + ", 0)")
    check("Context check not completed" in card
          and "No material restriction omission detected" not in card
          and "Material restriction omitted" not in card,
          "context card: 'Context check not completed', and nothing else")
    card = render("renderAcademicClaimContext("
                  + json.dumps(occurrence(control, CLAIM_1)) + ", 0)")
    check("No material restriction omission detected" in card
          and "not completed" not in card,
          "context card: a valid False keeps its label")

    card = render("renderAcademicSourceClaim("
                  + json.dumps(failed_source["source_claims"][0]) + ", 0)")
    check("<strong>Claim assessment:</strong> not completed" in card
          and "Show located source evidence" in card,
          "source card: 'Claim assessment: not completed', with the evidence kept")
    card = render("renderAcademicSourceClaim("
                  + json.dumps(supported["source_claims"][0]) + ", 0)")
    check("Claim supported" in card and "not completed" not in card,
          "source card: a valid assessment keeps its label")

    for name, body in (("context", failed_context), ("source", failed_source)):
        page = render("renderAcademicCheckFurther("
                      + json.dumps(body["check_further"]) + ", '', '')")
        reader_part = page.split('<details class="technical-details">')[0]
        check(cf.INCOMPLETE_SUMMARY in reader_part
              and "Error" not in reader_part,
              f"{name} failure: the generalised wording, and no error text, "
              "at reader level")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
