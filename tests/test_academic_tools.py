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


print("\n[5] matching DOI and title identities remain coherent")

try:
    at.verify_reference = lambda **kwargs: at.VerificationResult(
        status="verified",
        candidate=jackson_crossref,
        reasons=["The supplied citation metadata match the DOI record."],
        claim_verified=False,
        related_candidate=None,
    )

    at.resolve_doi = lambda doi: jackson_crossref
    at.resolve_openalex_doi = lambda doi: jackson_openalex
    at.search_crossref = (
        lambda title, author=None, rows=5: [jackson_crossref]
    )
    at.search_openalex = (
        lambda title, rows=5: [jackson_openalex]
    )

    coherent = at.verify_academic_reference(
        title=JACKSON_TITLE,
        author="Jackson",
        year=2015,
        venue="Research Synthesis Methods",
        doi="10.1002/jrsm.1162",
    )

finally:
    at.verify_reference = original_verify
    at.resolve_doi = original_resolve_doi
    at.resolve_openalex_doi = original_resolve_openalex_doi
    at.search_crossref = original_search_crossref
    at.search_openalex = original_search_openalex


check("Crossref verification is verified",
      coherent.crossref_verification.status == "verified",
      coherent.crossref_verification.status)

check("matching DOI identity is corroborated",
      coherent.doi_corroboration is not None
      and coherent.doi_corroboration.status == "corroborated",
      coherent.doi_corroboration.status
      if coherent.doi_corroboration else "None")

check("matching title identity is corroborated",
      coherent.related_corroboration is not None
      and coherent.related_corroboration.status == "corroborated",
      coherent.related_corroboration.status
      if coherent.related_corroboration else "None")

check("matching DOI and title do not create an identity conflict",
      coherent.identity_conflict is False)

check("coherent bibliographic identity still does not verify the claim",
      coherent.claim_verified is False)


print("\n[6] bibliographic evidence never becomes claim verification")
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



print("\n[7] supplied bibliographic metadata disambiguate exact-title works")

little_book = at.ReferenceCandidate(
    title="Statistical Analysis with Missing Data",
    authors=["Roderick J. A. Little", "Donald B. Rubin"],
    year=2002,
    venue="Wiley series in probability and statistics",
    doi="10.1002/9781119013563",
    work_type="book",
    source="crossref",
    title_similarity=1.0,
)

little_review = at.ReferenceCandidate(
    title="Statistical Analysis With Missing Data",
    authors=["Nicole A Lazar"],
    year=2003,
    venue="Technometrics",
    doi="10.1198/tech.2003.s167",
    work_type="journal-article",
    source="crossref",
    title_similarity=1.0,
)

little_author = "Little, R. J. A. and Rubin, D. B."

check(
    "Little/Rubin book outranks exact-title journal item",
    at._candidate_rank(
        little_book,
        author=little_author,
        year=2002,
    )
    > at._candidate_rank(
        little_review,
        author=little_author,
        year=2002,
    ),
    (
        at._candidate_rank(
            little_book,
            author=little_author,
            year=2002,
        ),
        at._candidate_rank(
            little_review,
            author=little_author,
            year=2002,
        ),
    ),
)


rubin_book = at.ReferenceCandidate(
    title="Multiple Imputation for Nonresponse in Surveys",
    authors=["Donald B. Rubin"],
    year=1987,
    venue="Wiley series in probability and statistics",
    doi="10.1002/9780470316696",
    work_type="book",
    source="crossref",
    title_similarity=1.0,
)

rubin_review = at.ReferenceCandidate(
    title="Multiple Imputation for Nonresponse in Surveys.",
    authors=["Roger A. Sugden", "D. B. Rubin"],
    year=1988,
    venue=(
        "Journal of the Royal Statistical Society. "
        "Series A (Statistics in Society)"
    ),
    doi="10.2307/2983027",
    work_type="journal-article",
    source="crossref",
    title_similarity=1.0,
)

check(
    "Rubin book outranks exact-title journal item",
    at._candidate_rank(
        rubin_book,
        author="Rubin, D. B.",
        year=1987,
    )
    > at._candidate_rank(
        rubin_review,
        author="Rubin, D. B.",
        year=1987,
    ),
    (
        at._candidate_rank(
            rubin_book,
            author="Rubin, D. B.",
            year=1987,
        ),
        at._candidate_rank(
            rubin_review,
            author="Rubin, D. B.",
            year=1987,
        ),
    ),
)



print("\n[8] public verification pipeline selects intended exact-title identity")

original_search_crossref = at.search_crossref
original_search_openalex = at.search_openalex

try:
    at.search_crossref = (
        lambda title, author=None, rows=5: [
            little_review,
            little_book,
        ]
    )
    at.search_openalex = (
        lambda title, rows=5: [
            at.ReferenceCandidate(
                title="Statistical Analysis with Missing Data",
                authors=["Roderick J. A. Little", "Donald B. Rubin"],
                year=2002,
                venue="Wiley series in probability and statistics",
                doi="10.1002/9781119013563",
                work_type="book",
                source="openalex",
                title_similarity=1.0,
            )
        ]
    )

    little_verification = at.verify_reference(
        title="Statistical Analysis with Missing Data",
        author="Little, R. J. A. and Rubin, D. B.",
        year=2002,
        venue="Wiley series in probability and statistics",
    )

    little_academic = at.verify_academic_reference(
        title="Statistical Analysis with Missing Data",
        author="Little, R. J. A. and Rubin, D. B.",
        year=2002,
        venue="Wiley series in probability and statistics",
    )

finally:
    at.search_crossref = original_search_crossref
    at.search_openalex = original_search_openalex


check(
    "Crossref verification selects Little/Rubin book",
    little_verification.candidate is not None
    and little_verification.candidate.doi
    == "10.1002/9781119013563",
    little_verification.to_dict(),
)

check(
    "Little/Rubin book is bibliographically verified",
    little_verification.status == "verified",
    little_verification.status,
)

check(
    "cross-database title search selects same book identity",
    little_academic.related_corroboration is not None
    and little_academic.related_corroboration.crossref is not None
    and little_academic.related_corroboration.openalex is not None
    and little_academic.related_corroboration.crossref.doi
    == "10.1002/9781119013563"
    and little_academic.related_corroboration.openalex.doi
    == "10.1002/9781119013563",
    (
        little_academic.related_corroboration.to_dict()
        if little_academic.related_corroboration
        else "None"
    ),
)

check(
    "Little/Rubin title identity is corroborated",
    little_academic.related_corroboration is not None
    and little_academic.related_corroboration.status == "corroborated",
    (
        little_academic.related_corroboration.status
        if little_academic.related_corroboration
        else "None"
    ),
)

check(
    "bibliographic corroboration still does not verify claim support",
    little_academic.claim_verified is False,
)



print("\n[9] abbreviated venue metadata remains compatible")

original_search_crossref = at.search_crossref

try:
    at.search_crossref = (
        lambda title, author=None, rows=5: [
            little_review,
            little_book,
        ]
    )

    abbreviated_venue = at.verify_reference(
        title="Statistical Analysis with Missing Data",
        author="Little, R. J. A. and Rubin, D. B.",
        year=2002,
        venue="Wiley",
    )

    incompatible_venue = at.verify_reference(
        title="Statistical Analysis with Missing Data",
        author="Little, R. J. A. and Rubin, D. B.",
        year=2002,
        venue="Technometrics",
    )

finally:
    at.search_crossref = original_search_crossref


check(
    "publisher abbreviation does not reject matching book identity",
    abbreviated_venue.status == "verified"
    and abbreviated_venue.candidate is not None
    and abbreviated_venue.candidate.doi
    == "10.1002/9781119013563",
    abbreviated_venue.to_dict(),
)

check(
    "unrelated venue still rejects otherwise matching identity",
    incompatible_venue.status == "not_verified"
    and incompatible_venue.candidate is None,
    incompatible_venue.to_dict(),
)



print("\n[10] author matching does not accept incidental token overlap")

particle_candidate = at.ReferenceCandidate(
    title="Synthetic Work",
    authors=["Jan van der Meer"],
    year=2020,
    venue="Example Journal",
    doi=None,
    work_type="journal-article",
)

unrelated_particle_candidate = at.ReferenceCandidate(
    title="Synthetic Work",
    authors=["Anna van Dijk"],
    year=2020,
    venue="Example Journal",
    doi=None,
    work_type="journal-article",
)

initial_candidate = at.ReferenceCandidate(
    title="Synthetic Work",
    authors=["David Brown"],
    year=2020,
    venue="Example Journal",
    doi=None,
    work_type="journal-article",
)

check(
    "matching surname with fuller supplied citation remains accepted",
    at._author_matches(
        little_book,
        "Little, R. J. A. and Rubin, D. B.",
    ),
)

check(
    "Rubin surname remains accepted",
    at._author_matches(
        rubin_book,
        "Rubin, D. B.",
    ),
)

check(
    "shared name particle alone does not establish author match",
    not at._author_matches(
        unrelated_particle_candidate,
        "Jan van der Meer",
    ),
)

check(
    "shared given-name initial alone does not establish author match",
    not at._author_matches(
        initial_candidate,
        "D. Smith",
    ),
)

check(
    "multi-token surname remains matchable",
    at._author_matches(
        particle_candidate,
        "van der Meer, J.",
    ),
)



print("\n[11] author-constrained discovery supplements title-only Crossref results")

little_title_only = [
    at.ReferenceCandidate(
        title="Statistical Analysis with Missing Data.",
        authors=["Martin G. Gibson", "R. J. A. Little", "D. B. Rubin"],
        year=1989,
        venue="The Statistician",
        doi="10.2307/2349029",
        work_type="journal-article",
        title_similarity=1.0,
    ),
    at.ReferenceCandidate(
        title="Statistical Analysis With Missing Data",
        authors=["Nicole A Lazar"],
        year=2003,
        venue="Technometrics",
        doi="10.1198/tech.2003.s167",
        work_type="journal-article",
        title_similarity=1.0,
    ),
]

little_author_constrained = [
    little_book,
    little_title_only[0],
]

openalex_little_book = at.ReferenceCandidate(
    title="Statistical Analysis with Missing Data",
    authors=["Roderick J. A. Little", "Donald B. Rubin"],
    year=2002,
    venue="Wiley series in probability and statistics",
    doi="10.1002/9781119013563",
    work_type="book",
    source="openalex",
    title_similarity=1.0,
)

original_search_crossref = at.search_crossref
original_search_openalex = at.search_openalex

try:
    def search_crossref_live_failure(title, author=None, rows=5):
        if author:
            return little_author_constrained
        return little_title_only

    at.search_crossref = search_crossref_live_failure
    at.search_openalex = (
        lambda title, rows=5: [openalex_little_book]
    )

    little_union_verification = at.verify_reference(
        title="Statistical Analysis with Missing Data",
        author="Little, R. J. A., & Rubin, D. B.",
        year=2002,
        venue="Wiley",
    )

    little_union_academic = at.verify_academic_reference(
        title="Statistical Analysis with Missing Data",
        author="Little, R. J. A., & Rubin, D. B.",
        year=2002,
        venue="Wiley",
    )

finally:
    at.search_crossref = original_search_crossref
    at.search_openalex = original_search_openalex


check(
    "author-constrained discovery recovers book omitted by title-only search",
    little_union_verification.status == "verified"
    and little_union_verification.candidate is not None
    and little_union_verification.candidate.doi
    == "10.1002/9781119013563",
    little_union_verification.to_dict(),
)

check(
    "corroboration uses recovered Crossref book identity",
    little_union_academic.related_corroboration is not None
    and little_union_academic.related_corroboration.status == "corroborated"
    and little_union_academic.related_corroboration.crossref is not None
    and little_union_academic.related_corroboration.crossref.doi
    == "10.1002/9781119013563"
    and little_union_academic.related_corroboration.openalex is not None
    and little_union_academic.related_corroboration.openalex.doi
    == "10.1002/9781119013563",
    (
        little_union_academic.related_corroboration.to_dict()
        if little_union_academic.related_corroboration
        else "None"
    ),
)

check(
    "recovered bibliographic identity still does not verify claim support",
    little_union_academic.claim_verified is False,
)


print()
if fails:
    print(f"{len(fails)} FAILURE(S): {fails}")
    sys.exit(1)

print("All academic-tools tests passed.")
