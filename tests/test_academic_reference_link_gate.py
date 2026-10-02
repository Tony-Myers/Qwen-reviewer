#!/usr/bin/env python3
"""
Which model-proposed references the reader sees, and as what.

    python3 tests/test_academic_reference_link_gate.py

Reproduces the live case of 2 October 2026. Asked about the number of
imputations, Academic Chat listed "Comparison of two populations of curves
with an application in neuronal data analysis" (Behseta & Chenouri, 2011,
doi:10.1002/sim.4192) as a reference. Nothing in the answer cited it and no
source claim pointed to it, and the citation notice counted it as a source
"cited in this answer". The page also showed the record the proposed DOI
resolved to in place of what the model proposed, so a hallucinated
reference looked like a real but unrelated paper.

Two application-owned rules, no model judgement:

  1. a proposed reference is the answer's reference only when a source claim
     points to it (claim.reference_index); the others stay in the technical
     details, and the citation notice ignores them;
  2. a record verification attaches without accepting it -- a probable
     match, or the record a DOI resolves to when the details conflict -- is
     shown beside the proposed reference, never in its place.

Run through the real orchestrator, evidence layer and the page's own
renderers (under Node when installed). Only the bibliographic lookups are
replaced, so every case is deterministic. Checked:

  A. an unlinked, unverified proposal is not listed as a reference, raises
     no citation notice, and is kept in the technical details;
  B. a linked, verified reference is shown normally;
  C. a linked, unverified reference is still shown, with its status, and
     raises the citation notice;
  D. a proposal whose DOI resolves to a different publication keeps its own
     identity, and the DOI's record is shown separately as a different
     publication, in the technical details as well;
  E. curated further reading is unaffected.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import academic_chat                          # noqa: E402
import academic_check_further as cf           # noqa: E402
import academic_orchestrator as orchestrator  # noqa: E402
import academic_technical                     # noqa: E402
import reviewer_notes as rn                   # noqa: E402
from academic_tools import (                  # noqa: E402
    AcademicReferenceResult, ReferenceCandidate, VerificationResult)

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


def record(title, authors, year, venue, doi):
    return ReferenceCandidate(title=title, authors=authors, year=year,
                              venue=venue, doi=doi, work_type="journal-article")


BEHSETA = record("Comparison of two populations of curves with an application "
                 "in neuronal data analysis", ["Sam Behseta", "Shojaeddin Chenouri"],
                 2011, "Statistics in Medicine", "10.1002/sim.4192")
STERNE = record("Multiple imputation for missing data in epidemiological and "
                "clinical research: potential and pitfalls",
                ["J. A C Sterne", "I. R White"], 2009, "BMJ", "10.1136/bmj.b2393")
RUBIN = record("Multiple Imputation for Nonresponse in Surveys", ["Donald B. Rubin"],
               1987, "Wiley Series in Probability and Statistics",
               "10.1002/9780470316696")
CONFLICT_RECORD = record("An unrelated paper on survival curves", ["Ann Other"],
                         2015, "Biometrics", "10.1111/biom.0001")

# The model's proposals, in draft order.
UNLINKED_CONFLICT = academic_chat.AcademicReference(
    title="Multiple imputation using chained equations: issues and guidance "
          "for practice", author="White, I. R.", year=2011,
    venue="Statistics in Medicine", doi="10.1002/sim.4192")
LINKED_VERIFIED = academic_chat.AcademicReference(
    title=STERNE.title, author="Sterne, J. A. C.", year=2009, venue="BMJ",
    doi="10.1136/bmj.b2393")
LINKED_UNVERIFIED = academic_chat.AcademicReference(
    title="Multiple Imputation for Nonresponse in Surveys", author="Rubin, D. B.",
    year=1987, venue="John Wiley & Sons", doi=None)
LINKED_CONFLICT = academic_chat.AcademicReference(
    title="How many imputations are really needed?", author="Graham, J. W.",
    year=2007, venue="Prevention Science", doi="10.1111/biom.0001")

VERIFICATIONS = {
    UNLINKED_CONFLICT.title: ("metadata_conflict", BEHSETA, None),
    LINKED_VERIFIED.title: ("verified", STERNE, None),
    LINKED_UNVERIFIED.title: ("not_verified", None, RUBIN),
    LINKED_CONFLICT.title: ("metadata_conflict", CONFLICT_RECORD, None),
}


def reference_verifier(*, title, author, year, venue, doi):
    status, candidate, related = VERIFICATIONS[title]
    return AcademicReferenceResult(
        crossref_verification=VerificationResult(
            status=status, candidate=candidate, reasons=["Synthetic lookup."],
            related_candidate=related),
        doi_corroboration=None, related_corroboration=None,
        identity_conflict=False, reasons=["Synthetic lookup."])


def first_stage(references, source_claims):
    draft = academic_chat.AcademicDraft(
        answer_draft="An answer about the number of imputations.",
        references=list(references), source_claims=list(source_claims),
        technical_claims=[])
    return orchestrator.assess_academic_draft(
        draft,
        local_guidance=orchestrator.LocalGuidanceResult(passages=[]),
        reference_verifier=reference_verifier,
        technical_verifier=academic_technical.verify_technical_claim)


ALL = [UNLINKED_CONFLICT, LINKED_VERIFIED, LINKED_UNVERIFIED, LINKED_CONFLICT]
CLAIMS = [academic_chat.SourceClaim(claim="Claim relying on reference.",
                                    reference_index=i) for i in (1, 2, 3)]
INDEX = orchestrator.methodological_notes_index()

# ===========================================================================
print("\n[evidence layer] the citation notice counts linked references only")
only_unlinked = first_stage([UNLINKED_CONFLICT], [])
d = cf.assess_check_further(only_unlinked, INDEX).to_dict()
check(d["citation_notice"] is None,
      "A: an unlinked, unverified proposal raises no citation notice")
check(any("Multiple imputation using chained equations" in x
          for x in d["diagnostics"]["unlinked_references"]),
      "A: it is listed in the diagnostics as a proposal not linked to any claim")

verified_only = first_stage([LINKED_VERIFIED],
                            [academic_chat.SourceClaim(claim="c", reference_index=0)])
d = cf.assess_check_further(verified_only, INDEX).to_dict()
check(d["citation_notice"] is None and d["diagnostics"]["unlinked_references"] == [],
      "B: a linked, verified reference raises no notice and is not 'unlinked'")

full = first_stage(ALL, CLAIMS)
d_full = cf.assess_check_further(full, INDEX).to_dict()
notice = d_full["citation_notice"] or {}
check(notice.get("message", "").startswith(
          "Some sources given in support of this answer could not be matched "
          "to a published record."),
      "C: linked, unverified references raise the notice, worded as sources "
      "given in support of the answer")
check("cited in this answer" not in notice.get("message", ""),
      "C: the notice does not claim the answer cites them")
check(not any("chained equations" in x for x in notice.get("unmatched", [])),
      "A: the unlinked proposal is not among the sources it names")
check(cf.linked_reference_indices(full) == {1, 2, 3},
      "the link is read from the source claims' reference_index")

# ===========================================================================
print("\n[further reading] curated sources are unaffected")
RE = ("Missing Data, Dropout and Analysis Populations",
      "How does FMI affect relative efficiency?")


def routed(references, source_claims):
    passage = rn.Passage(RE[0], RE[1], "text", 0.5)
    result = NS(
        release=NS(safe_to_present=True,
                   status="release_allowed_with_unverified_claims", reasons=[]),
        technical_claims=[NS(claim=NS(statement="X"),
                             verification=NS(status="not_technically_verified"),
                             methodological_consistency=NS(
                                 status="methodological_consistency_not_established",
                                 passages=[passage], reasons=["r"]))],
        discovered_claim_assessments=[], references=references,
        source_claims=source_claims,
        local_guidance=NS(passages=[passage]))
    return cf.assess_check_further(result, INDEX).to_dict()


without = routed([], [])
with_refs = routed(full.references, full.source_claims)
check(without["further_reading"] and
      without["further_reading"] == with_refs["further_reading"]
      and without["source_count"] == with_refs["source_count"],
      "E: the same curated further reading with or without generated references")
check(not any("sim.4192" in json.dumps(g) for g in with_refs["further_reading"]),
      "E: no generated reference enters the curated further reading")

# ===========================================================================
print("\n[page] what the reader and the technical details show")
node = shutil.which("node")
if not node:
    print("SKIP: Node is not installed, so the rendering checks did not run.")
else:
    html = (ROOT / "app" / "chat.html").read_text(encoding="utf-8")
    page_functions = re.findall(r"^function \w+\(.*?\n}\n", html, re.S | re.M)
    payload = full.to_dict()
    payload["check_further"] = d_full
    script = "\n".join(page_functions) + (
        f"\nprocess.stdout.write(renderAcademicEvidence({json.dumps(payload)}));")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    run = subprocess.run([node, f.name], capture_output=True, text=True, timeout=30)
    Path(f.name).unlink()
    out = run.stdout
    tech = out.find("Technical checking details")
    reader, technical = out[:tech], out[tech:]
    check(run.returncode == 0 and tech > 0, "the evidence renders")

    references_at = reader.find("<h3>References</h3>")
    reader_refs = reader[references_at:]
    check(references_at > 0, "the reader-facing References section is present")
    check("chained equations" not in reader and "Behseta" not in reader,
          "A: the unlinked proposal and its DOI's record are not shown to the reader")
    check("Proposed references not linked to any claim" in technical
          and "chained equations" in technical,
          "A: the unlinked proposal is kept in the technical details")

    check(STERNE.title in reader_refs and "Bibliographic identity verified" in reader_refs
          and "doi:10.1136/bmj.b2393" in reader_refs,
          "B: the linked, verified reference is shown normally, with its DOI")

    check("Multiple Imputation for Nonresponse in Surveys" in reader_refs
          and "Rubin, D. B." in reader_refs and "John Wiley &amp; Sons" in reader_refs,
          "C: the linked, unverified reference is shown with its proposed details")
    check(reader_refs.count("Bibliographic identity not independently established") == 2,
          "C: unverified references carry their status")
    check("Citation check:" in reader and "could not be matched" in reader,
          "C: the reader sees the citation notice")

    graham = reader_refs[reader_refs.find("How many imputations are really needed?"):]
    check(reader_refs.find("How many imputations are really needed?") > 0
          and "Graham, J. W." in graham.split("academic-related-record")[0],
          "D: a linked proposal with a conflicting DOI keeps its own title and author")
    label_at = graham.find("The DOI given resolves to a different publication:")
    check(label_at >= 0
          and graham.find("An unrelated paper on survival curves") > label_at,
          "D: the DOI's record is shown separately, labelled as a different publication")
    check(reader_refs.find("An unrelated paper on survival curves")
          > reader_refs.find("How many imputations are really needed?"),
          "D: the resolved record never replaces the proposed title")
    check('href="https://doi.org/10.1111%2Fbiom.0001"' not in
          graham.split("academic-related-record")[0],
          "D: the conflicting DOI is not linked as the proposal's own DOI")
    unlinked_tech = technical[technical.find("Proposed references not linked"):]
    check("Multiple imputation using chained equations" in unlinked_tech
          and "White, I. R." in unlinked_tech
          and "The DOI given resolves to a different publication:" in unlinked_tech
          and "Behseta" in unlinked_tech,
          "D: in the technical details, the proposal and the publication its DOI "
          "resolves to are both visible, as different identities")
    check(technical.find("Comparison of two populations of curves")
          > technical.find("Multiple imputation using chained equations"),
          "D: the Behseta record appears only after, and apart from, the proposal")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
