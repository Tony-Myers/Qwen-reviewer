#!/usr/bin/env python3
"""
Bibliographic matching reads a record by its type, not as a journal article.

    python3 tests/test_academic_book_matching.py

Crossref records a book's publisher and series separately, keeps a chapter's
series and containing book together in container-title, and often splits a
book's title into title and subtitle. Matching used to take container-title[0]
as the venue for every record, ignore publisher and subtitle, and score the
"monograph" type below an unknown one. So a correct proposal for Rubin (1987)
with venue "John Wiley & Sons" failed against the series name, Pearl's
"Causality: Models, Reasoning, and Inference" failed against the title
"Causality", and a chapter's containing book was never compared.

The records below are shaped as Crossref returned them on 2 October 2026
(type, title, subtitle, container-title in its order, publisher, author,
dates, DOI). They pass through the real HTTP-to-candidate extraction and
verification path; only the network request is replaced, and a search
returns just the fields its select= parameter asks for, as Crossref does.
The book-review records are constructed for the negative cases and labelled
as such. Checked:

  1. Rubin (1987): "John Wiley & Sons", "Wiley", the series name and no
     venue all verify, through both search and DOI;
  2. Pearl (2009): the full title with subtitle and "Cambridge University
     Press" verify, and corroboration accepts the differently split title;
  3. Akaike's chapter: the containing book, the publisher, the series and
     no venue all verify;
  4. negatives: an incompatible venue (Technometrics) does not verify the
     book, an unrelated publisher does not match, and a same-title book
     review does not outrank the book, whether the book is typed "book" or
     "monograph"; publisher names are checked pair by pair, including that
     a university press matches only another university press. Known
     non-matches (Taylor & Francis vs Informa, Chapman & Hall vs CRC Press)
     are out of scope;
  5. journals: exact names and punctuation variants still match, and
     abbreviations behave as before (not matched; out of scope);
  6. a DOI that resolves to a different publication is still a metadata
     conflict, kept apart from the proposal.
"""
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_tools as at  # noqa: E402

failures = 0


def check(condition, label, detail=""):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label
          + (f"  [{detail}]" if not condition and detail else ""))
    if not condition:
        failures += 1


# ---- records as Crossref returned them ------------------------------------
RUBIN_1987 = {
    "DOI": "10.1002/9780470316696", "type": "monograph",
    "title": ["Multiple Imputation for Nonresponse in Surveys"], "subtitle": [],
    "container-title": ["Wiley Series in Probability and Statistics"],
    "publisher": "Wiley",
    "author": [{"given": "Donald B.", "family": "Rubin", "sequence": "first"}],
    "ISBN": ["9780471087052", "9780470316696"],
    "issued": {"date-parts": [[1987, 6, 9]]},
    "published-print": {"date-parts": [[1987, 6, 9]]},
    "published-online": {"date-parts": [[2008, 5, 27]]},
    "published": {"date-parts": [[1987, 6, 9]]},
}
PEARL_2009 = {
    "DOI": "10.1017/cbo9780511803161", "type": "monograph",
    "title": ["Causality"], "subtitle": ["Models, Reasoning, and Inference"],
    "container-title": [], "publisher": "Cambridge University Press",
    "author": [{"given": "Judea", "family": "Pearl", "sequence": "first"}],
    "issued": {"date-parts": [[2009, 9, 14]]},
    "published-print": {"date-parts": [[2009, 9, 14]]},
    "published-online": {"date-parts": [[2013, 3, 5]]},
}
AKAIKE_CHAPTER = {
    "DOI": "10.1007/978-1-4612-1694-0_16", "type": "book-chapter",
    "title": ["A New Look at the Statistical Model Identification"], "subtitle": [],
    "container-title": ["Springer Series in Statistics",
                        "Selected Papers of Hirotugu Akaike"],
    "publisher": "Springer New York",
    "author": [{"given": "Hirotugu", "family": "Akaike", "sequence": "first"}],
    "issued": {"date-parts": [[1974]]}, "published-print": {"date-parts": [[1974]]},
    "page": "215-222",
}
STERNE_BMJ = {
    "DOI": "10.1136/bmj.b2393", "type": "journal-article",
    "title": ["Multiple imputation for missing data in epidemiological and "
              "clinical research: potential and pitfalls"],
    "container-title": ["BMJ"], "publisher": "BMJ",
    "author": [{"given": "J. A C", "family": "Sterne"}, {"given": "I. R", "family": "White"}],
    "issued": {"date-parts": [[2009, 6, 29]]},
    "published-print": {"date-parts": [[2009, 9, 1]]},
}
MOLENBERGHS_JRSSB = {
    "DOI": "10.1111/j.1467-9868.2007.00640.x", "type": "journal-article",
    "title": ["Every Missingness not at Random Model Has a Missingness at "
              "Random Counterpart with Equal Fit"],
    "container-title": ["Journal of the Royal Statistical Society Series B: "
                        "Statistical Methodology"],
    "publisher": "Oxford University Press (OUP)",
    "author": [{"given": "Geert", "family": "Molenberghs"},
               {"given": "Caroline", "family": "Beunckens"}],
    "issued": {"date-parts": [[2008, 2, 6]]},
    "published-print": {"date-parts": [[2008, 4, 1]]},
}
BEHSETA_SIM = {
    "DOI": "10.1002/sim.4192", "type": "journal-article",
    "title": ["Comparison of two populations of curves with an application in "
              "neuronal data analysis"],
    "container-title": ["Statistics in Medicine"], "publisher": "Wiley",
    "author": [{"given": "Sam", "family": "Behseta"},
               {"given": "Shojaeddin", "family": "Chenouri"}],
    "issued": {"date-parts": [[2011, 2, 22]]},
    "published-print": {"date-parts": [[2011, 5, 30]]},
}
WRW_SIM = {
    "DOI": "10.1002/sim.4067", "type": "journal-article",
    "title": ["Multiple imputation using chained equations: Issues and guidance "
              "for practice"],
    "container-title": ["Statistics in Medicine"], "publisher": "Wiley",
    "author": [{"given": "Ian R.", "family": "White"},
               {"given": "Patrick", "family": "Royston"},
               {"given": "Angela M.", "family": "Wood"}],
    "issued": {"date-parts": [[2010, 11, 30]]},
    "published-print": {"date-parts": [[2011, 2, 20]]},
}
# Constructed negatives: a journal book review carrying the book's title.
RUBIN_REVIEW = {
    "DOI": "10.0000/constructed.review.1987", "type": "journal-article",
    "title": ["Multiple Imputation for Nonresponse in Surveys"],
    "container-title": ["Technometrics"], "publisher": "Informa UK Limited",
    "author": [{"given": "A.", "family": "Reviewer"}],
    "issued": {"date-parts": [[1988]]}, "published-print": {"date-parts": [[1988]]},
}

RECORDS = {r["DOI"].lower(): r for r in
           (RUBIN_1987, PEARL_2009, AKAIKE_CHAPTER, STERNE_BMJ, MOLENBERGHS_JRSSB,
            BEHSETA_SIM, WRW_SIM, RUBIN_REVIEW)}
SEARCH_RESULTS = {}   # set per case: the items a title search returns
requested_selects = []


def fake_get_json(url, timeout=10.0, max_attempts=3):
    parsed = urlparse(url)
    if parsed.path.startswith("/works/"):
        doi = unquote(parsed.path[len("/works/"):]).lower()
        if doi not in RECORDS:
            raise RuntimeError("Crossref request failed: HTTP Error 404: Not Found")
        return {"message": dict(RECORDS[doi])}
    query = parse_qs(parsed.query)
    select = query.get("select", [""])[0].split(",")
    requested_selects.append(select)
    items = [{k: v for k, v in item.items() if k in select}
             for item in SEARCH_RESULTS.get("items", [])]
    return {"message": {"items": items}}


at._get_json = fake_get_json


def by_search(items, **proposal):
    SEARCH_RESULTS["items"] = items
    return at.verify_reference(**proposal)


def verified_as(result, doi):
    return (result.status == "verified" and result.candidate is not None
            and result.candidate.doi == doi)


# ===========================================================================
print("\n[0] extraction keeps the fields matching reads, and search asks for them")
rubin = at._extract_candidate(RUBIN_1987)
check(rubin.venue == "Wiley Series in Probability and Statistics"
      and rubin.publisher == "Wiley" and rubin.subtitle == ""
      and rubin.container_titles == ["Wiley Series in Probability and Statistics"]
      and rubin.work_type == "monograph",
      "Rubin: venue unchanged (first container-title); publisher and containers kept")
akaike = at._extract_candidate(AKAIKE_CHAPTER)
check(akaike.container_titles == ["Springer Series in Statistics",
                                  "Selected Papers of Hirotugu Akaike"]
      and akaike.publisher == "Springer New York",
      "Akaike chapter: series and containing book both kept, in Crossref's order")
pearl = at._extract_candidate(PEARL_2009)
check(pearl.title == "Causality" and pearl.subtitle == "Models, Reasoning, and Inference",
      "Pearl: title and subtitle kept separately")
by_search([RUBIN_1987], title="Multiple Imputation for Nonresponse in Surveys")
check(requested_selects and {"subtitle", "publisher"} <= set(requested_selects[-1]),
      "title search requests subtitle and publisher")

# ===========================================================================
print("\n[1] Rubin (1987): the overloaded venue may name publisher or series")
RUBIN_DOI = "10.1002/9780470316696"
for venue in ("John Wiley & Sons", "Wiley", "Wiley Series in Probability and Statistics", None):
    result = by_search([RUBIN_1987], title="Multiple Imputation for Nonresponse in Surveys",
                       author="Rubin, D. B.", year=1987, venue=venue)
    check(verified_as(result, RUBIN_DOI), f"search, venue {venue!r} verifies",
          f"{result.status}: {result.reasons}")
    result = at.verify_reference(title="Multiple Imputation for Nonresponse in Surveys",
                                 author="Rubin, D. B.", year=1987, venue=venue,
                                 doi=RUBIN_DOI)
    check(verified_as(result, RUBIN_DOI), f"DOI, venue {venue!r} verifies",
          f"{result.status}: {result.reasons}")

# ===========================================================================
print("\n[2] Pearl (2009): title split into title and subtitle")
PEARL_DOI = "10.1017/cbo9780511803161"
result = by_search([PEARL_2009], title="Causality: Models, Reasoning, and Inference",
                   author="Pearl, J.", year=2009, venue="Cambridge University Press")
check(verified_as(result, PEARL_DOI),
      "full title with subtitle and the publisher verify", f"{result.status}: {result.reasons}")
result = by_search([PEARL_2009], title="Causality", author="Pearl, J.", year=2009,
                   venue="Cambridge University Press")
check(verified_as(result, PEARL_DOI), "the main title alone also verifies",
      f"{result.status}: {result.reasons}")
result = at.verify_reference(title="Causality: Models, Reasoning, and Inference",
                             author="Pearl, J.", year=2009,
                             venue="Cambridge University Press", doi=PEARL_DOI)
check(verified_as(result, PEARL_DOI), "and through the DOI", f"{result.status}: {result.reasons}")
openalex_pearl = at.ReferenceCandidate(
    title="Causality: Models, Reasoning, and Inference", authors=["Judea Pearl"],
    year=2009, venue="", doi=PEARL_DOI, work_type="book", source="openalex")
corroboration = at.corroborate_candidates(at._extract_candidate(PEARL_2009), openalex_pearl)
check(corroboration.status == "corroborated",
      "cross-database corroboration accepts the same title split differently",
      corroboration.reasons)
result = by_search([PEARL_2009], title="Causality and Explanation in the Social Sciences",
                   author="Pearl, J.", year=2009)
check(result.status != "verified",
      "the title threshold is unchanged: a different title is not accepted",
      f"{result.status}")

# ===========================================================================
print("\n[3] Akaike's chapter: book, series or publisher")
AKAIKE_DOI = "10.1007/978-1-4612-1694-0_16"
for venue in ("Selected Papers of Hirotugu Akaike", "Springer New York", "Springer",
              "Springer Series in Statistics", None):
    result = by_search([AKAIKE_CHAPTER],
                       title="A new look at the statistical model identification",
                       author="Akaike, H.", year=1974, venue=venue)
    check(verified_as(result, AKAIKE_DOI), f"venue {venue!r} verifies the chapter",
          f"{result.status}: {result.reasons}")

# ===========================================================================
print("\n[4] negatives")
result = by_search([RUBIN_1987], title="Multiple Imputation for Nonresponse in Surveys",
                   author="Rubin, D. B.", year=1987, venue="Technometrics")
check(result.status == "not_verified",
      "Rubin with venue Technometrics is not verified", result.status)
result = by_search([PEARL_2009], title="Causality: Models, Reasoning, and Inference",
                   author="Pearl, J.", year=2009, venue="Oxford University Press")
check(result.status == "not_verified",
      "Pearl with venue Oxford University Press is not verified", result.status)
# Publisher names as proposals and Crossref give them. True: the same publisher.
PUBLISHER_PAIRS = [
    ("John Wiley & Sons", "Wiley", True),
    ("Wiley", "Wiley-Blackwell", True),
    ("Springer", "Springer New York", True),
    ("Springer-Verlag", "Springer Science and Business Media LLC", True),
    ("SAGE Publications", "SAGE", True),
    ("Elsevier", "Elsevier BV", True),
    ("Chapman & Hall/CRC", "Chapman and Hall/CRC", True),
    ("Cambridge University Press", "Cambridge University Press", True),
    ("Oxford University Press", "Oxford University Press (OUP)", True),
    ("Guilford Press", "The Guilford Press", True),
    ("Oxford University Press", "Cambridge University Press", False),
    ("University Press", "Cambridge University Press", False),
    ("Press", "MIT Press", False),
    ("Press", "Cambridge University Press", False),
    ("American Psychological Association", "American Statistical Association", False),
    # Demonstrated false positives before the university-press rule.
    ("Cambridge University Press", "Cambridge Scholars Publishing", False),
    ("Harvard University Press", "Harvard Business Review Press", False),
    ("New York University Press", "Springer New York", False),
]
for supplied, publisher, same in PUBLISHER_PAIRS:
    check(at._publisher_matches(supplied, publisher) is same,
          f"publisher {supplied!r} {'matches' if same else 'does not match'} {publisher!r}")
for label, book in (("monograph", RUBIN_1987), ("book", dict(RUBIN_1987, type="book"))):
    result = by_search([RUBIN_REVIEW, book],
                       title="Multiple Imputation for Nonresponse in Surveys",
                       author="Rubin, D. B.", year=1987)
    check(verified_as(result, RUBIN_DOI),
          f"a same-title book review does not outrank the book typed {label!r}",
          f"{result.status}: {result.candidate.doi if result.candidate else None}")
review = at._extract_candidate(RUBIN_REVIEW, query_title="Multiple Imputation for Nonresponse in Surveys")
book = at._extract_candidate(RUBIN_1987, query_title="Multiple Imputation for Nonresponse in Surveys")
check(at._candidate_rank(book, author="Rubin, D. B.", year=1987)
      > at._candidate_rank(review, author="Rubin, D. B.", year=1987),
      "the book outranks the review on author and year, before type is consulted")
check(at._candidate_rank(book, author=None, year=None)[3] == 2,
      "a monograph now scores as a book-level work (2), not as an unknown type (0)")

# ===========================================================================
print("\n[5] journals: unchanged")
result = by_search([STERNE_BMJ],
                   title="Multiple imputation for missing data in epidemiological and "
                         "clinical research: potential and pitfalls",
                   author="Sterne, J. A. C.", year=2009, venue="BMJ")
check(verified_as(result, "10.1136/bmj.b2393"), "exact journal name verifies", result.status)
result = by_search([MOLENBERGHS_JRSSB],
                   title="Every missingness not at random model has a missingness at "
                         "random counterpart with equal fit",
                   author="Molenberghs, G.", year=2008,
                   venue="Journal of the Royal Statistical Society: Series B "
                         "(Statistical Methodology)")
check(verified_as(result, "10.1111/j.1467-9868.2007.00640.x"),
      "a punctuation variant of the journal name verifies", result.status)
result = by_search([MOLENBERGHS_JRSSB],
                   title="Every missingness not at random model has a missingness at "
                         "random counterpart with equal fit",
                   author="Molenberghs, G.", year=2008,
                   venue="Oxford University Press")
check(result.status == "not_verified",
      "a journal article is not matched through its publisher", result.status)
result = by_search([STERNE_BMJ],
                   title="Multiple imputation for missing data in epidemiological and "
                         "clinical research: potential and pitfalls",
                   author="Sterne, J. A. C.", year=2009, venue="British Medical Journal")
check(result.status == "not_verified",
      "documented, out of scope: 'British Medical Journal' still does not match 'BMJ'",
      result.status)

# ===========================================================================
print("\n[6] a DOI belonging to a different publication is still a conflict")
SEARCH_RESULTS["items"] = [WRW_SIM]
result = at.verify_reference(
    title="Multiple imputation using chained equations: issues and guidance for practice",
    author="White, I. R.", year=2011, venue="Statistics in Medicine",
    doi="10.1002/sim.4192")
check(result.status == "metadata_conflict" and result.candidate is not None
      and result.candidate.doi == "10.1002/sim.4192",
      "the DOI's record is attached as a conflicting identity", result.status)
check(result.related_candidate is not None
      and result.related_candidate.doi == "10.1002/sim.4067",
      "and the publication the title identifies is kept separately")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
