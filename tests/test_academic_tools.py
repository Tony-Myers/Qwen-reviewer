#!/usr/bin/env python3
"""
Regression tests for academic bibliographic verification.

These tests deliberately make no network requests. Crossref and OpenAlex
records are represented by fixed candidates, and network-facing functions are
replaced during orchestration tests.

Bibliographic verification is not claim verification. A source may exist and
its metadata may be corroborated without establishing that it supports a
substantive academic claim.
"""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "app"),
)

import academic_tools as at


fails = []


def check(label, condition, detail=""):
    print(
        f"  {'PASS' if condition else 'FAIL'}  {label}"
        + (f"  {detail}" if not condition and detail else "")
    )
    if not condition:
        fails.append(label)


def candidate(
    *,
    title,
    authors,
    year,
    venue,
    doi,
    source,
):
    work_type = (
        "journal-article"
        if source == "crossref"
        else "article"
    )
    return at.ReferenceCandidate(
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        work_type=work_type,
        source=source,
    )


BAKER_TITLE = "A new approach to outliers in meta-analysis"
BAKER_DOI = "10.1007/s10729-007-9041-8"

baker_crossref = candidate(
    title=BAKER_TITLE,
    authors=["Rose Baker", "Dan Jackson"],
    year=2008,
    venue="Health Care Management Science",
    doi=BAKER_DOI,
    source="crossref",
)

baker_openalex = candidate(
    title=BAKER_TITLE,
    authors=["Rose Baker", "Dan Jackson"],
    year=2007,
    venue="Health Care Management Science",
    doi=BAKER_DOI,
    source="openalex",
)


print("\n[1] compatible metadata variation remains corroboration")
result = at.corroborate_candidates(
    baker_crossref,
    baker_openalex,
)

check("Baker record is corroborated",
      result.status == "corroborated", result.status)
check("same DOI recognised", result.same_doi is True)
check("complete author sets agree", result.author_agreement is True)
check("one-year publication difference retained",
      result.year_difference == 1, result.year_difference)
check("one-year difference is visible in reasons",
      any("differ by 1 year" in reason for reason in result.reasons),
      result.reasons)


print("\n[2] incompatible bibliographic identities are a conflict")
shadish = candidate(
    title="The meta-analytic big bang",
    authors=["William R. Shadish", "Jesse D. Lecy"],
    year=2015,
    venue="Research Synthesis Methods",
    doi="10.1002/jrsm.1132",
    source="crossref",
)

jackson_openalex = candidate(
    title=(
        "Approximate confidence intervals for moment-based estimators "
        "of the between-study variance in random effects meta-analysis"
    ),
    authors=["Dan Jackson", "Jack Bowden", "Rose Baker"],
    year=2015,
    venue="Research Synthesis Methods",
    doi="10.1002/jrsm.1162",
    source="openalex",
)

conflict = at.corroborate_candidates(
    shadish,
    jackson_openalex,
)

check("different works produce cross-source conflict",
      conflict.status == "cross_source_conflict",
      conflict.status)
check("different DOI recognised", conflict.same_doi is False)
check("different author sets recognised",
      conflict.author_agreement is False)


print("\n[3] missing-source states are explicit")
one = at.corroborate_candidates(baker_crossref, None)
none = at.corroborate_candidates(None, None)

check("one database only is single_source",
      one.status == "single_source", one.status)
check("neither database is no_source",
      none.status == "no_source", none.status)


print("\n[4] valid-but-wrong DOI is separated from title identity")

JACKSON_TITLE = (
    "Approximate confidence intervals for moment-based estimators "
    "of the between-study variance in random effects meta-analysis"
)

shadish_crossref = candidate(
    title="The meta-analytic big bang",
    authors=["William R. Shadish", "Jesse D. Lecy"],
    year=2015,
    venue="Research Synthesis Methods",
    doi="10.1002/jrsm.1132",
    source="crossref",
)

shadish_openalex = candidate(
    title="The meta-analytic big bang",
    authors=["William R. Shadish", "Jesse D. Lecy"],
    year=2015,
    venue="Research Synthesis Methods",
    doi="10.1002/jrsm.1132",
    source="openalex",
)

jackson_crossref = candidate(
    title=JACKSON_TITLE,
    authors=["Dan Jackson", "Jack Bowden", "Rose Baker"],
    year=2015,
    venue="Research Synthesis Methods",
    doi="10.1002/jrsm.1162",
    source="crossref",
)

jackson_openalex = candidate(
    title=JACKSON_TITLE,
    authors=["Dan Jackson", "Jack Bowden", "Rose Baker"],
    year=2015,
    venue="Research Synthesis Methods",
    doi="10.1002/jrsm.1162",
    source="openalex",
)

# Preserve originals so this test cannot contaminate later imports or tests.
original_verify = at.verify_reference
original_resolve_doi = at.resolve_doi
original_resolve_openalex_doi = at.resolve_openalex_doi
original_search_crossref = at.search_crossref
original_search_openalex = at.search_openalex

try:
    at.verify_reference = lambda **kwargs: at.VerificationResult(
        status="metadata_conflict",
        candidate=shadish_crossref,
        reasons=[
            "The supplied DOI resolves, but its metadata conflict "
            "with the supplied citation."
        ],
        claim_verified=False,
        related_candidate=jackson_crossref,
    )

    at.resolve_doi = lambda doi: shadish_crossref
    at.resolve_openalex_doi = lambda doi: shadish_openalex
    at.search_crossref = (
        lambda title, author=None, rows=5: [jackson_crossref]
    )
    at.search_openalex = (
        lambda title, rows=5: [jackson_openalex]
    )

    academic = at.verify_academic_reference(
        title=JACKSON_TITLE,
        author="Barker",
        year=2015,
        venue="Res. Syn. Meth.",
        doi="10.1002/jrsm.1132",
    )

finally:
    at.verify_reference = original_verify
    at.resolve_doi = original_resolve_doi
    at.resolve_openalex_doi = original_resolve_openalex_doi
    at.search_crossref = original_search_crossref
    at.search_openalex = original_search_openalex


check("Crossref verification retains metadata conflict",
      academic.crossref_verification.status == "metadata_conflict",
      academic.crossref_verification.status)

check("supplied DOI identity is corroborated",
      academic.doi_corroboration is not None
      and academic.doi_corroboration.status == "corroborated",
      academic.doi_corroboration.status
      if academic.doi_corroboration else "None")

check("title-derived identity is corroborated",
      academic.related_corroboration is not None
      and academic.related_corroboration.status == "corroborated",
      academic.related_corroboration.status
      if academic.related_corroboration else "None")

check("DOI-versus-title identity conflict established",
      academic.identity_conflict is True)

check("DOI side remains .1132",
      academic.doi_corroboration is not None
      and academic.doi_corroboration.crossref is not None
      and academic.doi_corroboration.crossref.doi
      == "10.1002/jrsm.1132")

check("title side recovers .1162",
      academic.related_corroboration is not None
      and academic.related_corroboration.crossref is not None
      and academic.related_corroboration.crossref.doi
      == "10.1002/jrsm.1162")

check("identity conflict is explained",
      any(
          "identify different publications" in reason
          for reason in academic.reasons
      ),
      academic.reasons)


print("\n[5] bibliographic evidence never becomes claim verification")
check("orchestration claim_verified remains false",
      academic.claim_verified is False)
check("Crossref claim_verified remains false",
      academic.crossref_verification.claim_verified is False)

for label, corroboration in (
    ("DOI corroboration", academic.doi_corroboration),
    ("title corroboration", academic.related_corroboration),
):
    check(
        f"{label} contains no claim-verification field",
        corroboration is not None
        and "claim_verified" not in corroboration.to_dict(),
        corroboration.to_dict() if corroboration else "None",
    )


print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)

print("All academic-tools tests passed.")
