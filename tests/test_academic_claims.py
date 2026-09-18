"""Regression tests for Academic Chat claim-support verification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_claims
import academic_tools


fails = []


def check(condition, message):
    if condition:
        print("PASS:", message)
    else:
        print("FAIL:", message)
        fails.append(message)


print("\n[1] source retrieval and claim support are separate concepts")

evidence = academic_claims.ClaimSupportResult(
    status="source_not_retrieved",
    source_status="not_retrieved",
    claim_status="not_assessed",
    doi="10.1000/example",
    evidence=[],
    reasons=["No substantive source text was retrieved."],
)

check(
    evidence.status == "source_not_retrieved",
    "failed retrieval has its own status",
)

check(
    evidence.claim_status == "not_assessed",
    "failed retrieval does not become unsupported claim",
)

check(
    evidence.evidence == [],
    "failed retrieval has no invented evidence",
)


print("\n[2] support is attached to a reference-claim pair")

supported = academic_claims.ClaimSupportResult(
    status="claim_supported",
    source_status="retrieved",
    claim_status="supported",
    doi="10.1000/example",
    evidence=[
        academic_claims.ClaimEvidence(
            text="Synthetic evidence passage.",
            locator="abstract",
            source="synthetic",
        )
    ],
    reasons=["Synthetic source passage supports the claim."],
)

check(
    supported.claim_status == "supported",
    "supported claim is represented explicitly",
)

check(
    len(supported.evidence) == 1,
    "support retains inspectable evidence",
)

check(
    supported.evidence[0].text == "Synthetic evidence passage.",
    "evidence text remains auditable",
)


print("\n[3] serialisation preserves provenance")

payload = supported.to_dict()

check(
    payload["status"] == "claim_supported",
    "overall support status serialises",
)

check(
    payload["source_status"] == "retrieved",
    "source retrieval status serialises separately",
)

check(
    payload["claim_status"] == "supported",
    "claim assessment serialises separately",
)

check(
    payload["doi"] == "10.1000/example",
    "bibliographic identifier remains attached",
)

check(
    payload["evidence"][0]["locator"] == "abstract",
    "evidence locator serialises",
)

check(
    payload["evidence"][0]["source"] == "synthetic",
    "evidence provenance serialises",
)



print("\n[4] source retrieval is driven by bibliographic identifier only")

retrieval_calls = []


def fake_source_retriever(doi):
    retrieval_calls.append(doi)
    return academic_claims.RetrievedSource(
        status="retrieved",
        doi=doi,
        source="synthetic",
        text="Synthetic scholarly source text.",
        locator="full_text",
        reasons=["Synthetic source retrieved."],
    )


retrieved = academic_claims.retrieve_source(
    doi="10.1000/example",
    retriever=fake_source_retriever,
)

check(
    retrieval_calls == ["10.1000/example"],
    "retriever receives DOI only",
)

check(
    retrieved.status == "retrieved",
    "successful retrieval is represented explicitly",
)

check(
    retrieved.text == "Synthetic scholarly source text.",
    "retrieved substantive text remains inspectable",
)

check(
    retrieved.locator == "full_text",
    "retrieved text type remains explicit",
)


print("\n[5] unavailable source remains distinct from unsupported claim")


def unavailable_source_retriever(doi):
    return academic_claims.RetrievedSource(
        status="not_retrieved",
        doi=doi,
        source="synthetic",
        text=None,
        locator=None,
        reasons=["No inspectable source text was available."],
    )


unavailable = academic_claims.retrieve_source(
    doi="10.1000/unavailable",
    retriever=unavailable_source_retriever,
)

check(
    unavailable.status == "not_retrieved",
    "unavailable source has explicit retrieval status",
)

check(
    unavailable.text is None,
    "unavailable source does not invent text",
)

check(
    unavailable.locator is None,
    "unavailable source does not invent a locator",
)



print("\n[6] OpenAlex discovery uses DOI and preserves source provenance")

openalex_calls = []


def fake_openalex_getter(doi):
    openalex_calls.append(doi)
    return {
        "doi": "https://doi.org/10.1000/example",
        "best_oa_location": {
            "landing_page_url": "https://example.org/article",
            "pdf_url": "https://example.org/article.pdf",
            "is_oa": True,
            "source": {
                "display_name": "Synthetic Journal"
            },
        },
    }


oa_source = academic_claims.discover_openalex_source(
    "10.1000/example",
    work_getter=fake_openalex_getter,
)

check(
    openalex_calls == ["10.1000/example"],
    "OpenAlex discovery boundary receives DOI only",
)

check(
    oa_source.doi == "10.1000/example",
    "retrieved source retains normalised DOI",
)

check(
    oa_source.source == "openalex",
    "discovered source records OpenAlex provenance",
)

check(
    oa_source.status == "location_found",
    "accessible source location is represented explicitly",
)

check(
    oa_source.pdf_url == "https://example.org/article.pdf",
    "OA PDF location is retained without downloading it",
)

check(
    oa_source.landing_page_url == "https://example.org/article",
    "landing-page location is retained",
)

check(
    oa_source.is_oa is True,
    "OpenAlex OA status is retained",
)


print("\n[7] existing OpenAlex work without accessible location remains explicit")


def fake_openalex_no_location(doi):
    return {
        "doi": "https://doi.org/10.1000/no-location",
        "best_oa_location": None,
    }


no_location = academic_claims.discover_openalex_source(
    "10.1000/no-location",
    work_getter=fake_openalex_no_location,
)

check(
    no_location.status == "location_not_found",
    "work without accessible location is not treated as retrieved",
)

check(
    no_location.doi == "10.1000/no-location",
    "DOI is retained when no accessible location is found",
)

check(
    no_location.landing_page_url is None,
    "missing location does not invent a landing-page URL",
)

check(
    no_location.pdf_url is None,
    "missing location does not invent a PDF URL",
)

check(
    no_location.is_oa is None,
    "missing location does not invent OA status",
)


print("\n[8] DOI absent from OpenAlex remains distinct from source retrieval")


def fake_openalex_missing_work(doi):
    return None


missing_work = academic_claims.discover_openalex_source(
    "10.1000/missing",
    work_getter=fake_openalex_missing_work,
)

check(
    missing_work.status == "location_not_found",
    "missing OpenAlex work has explicit no-location status",
)

check(
    missing_work.doi == "10.1000/missing",
    "supplied DOI is retained when OpenAlex has no work",
)

check(
    missing_work.landing_page_url is None,
    "missing work does not invent a landing-page URL",
)

check(
    missing_work.pdf_url is None,
    "missing work does not invent a PDF URL",
)

check(
    "no work" in " ".join(missing_work.reasons).lower(),
    "reason distinguishes missing work from inaccessible location",
)


print("\n[9] OpenAlex metadata lookup integrates with source discovery")

integration_urls = []
original_get_openalex_json = academic_tools._get_openalex_json


def fake_integration_openalex_json(url):
    integration_urls.append(url)
    return {
        "results": [
            {
                "title": "Synthetic Integrated Work",
                "doi": "https://doi.org/10.1000/integrated",
                "best_oa_location": {
                    "landing_page_url": "https://example.org/integrated",
                    "pdf_url": "https://example.org/integrated.pdf",
                    "is_oa": True,
                },
            }
        ]
    }


try:
    academic_tools._get_openalex_json = fake_integration_openalex_json

    integrated_location = academic_claims.discover_openalex_source(
        "10.1000/integrated",
        work_getter=academic_tools.get_openalex_work_by_doi,
    )
finally:
    academic_tools._get_openalex_json = original_get_openalex_json


check(
    len(integration_urls) == 1,
    "integrated discovery makes exactly one external metadata request",
)

check(
    len(integration_urls) == 1
    and "10.1000%2Fintegrated" in integration_urls[0],
    "integrated external request is driven by DOI",
)

check(
    integrated_location.status == "location_found",
    "raw OpenAlex work becomes an explicit source location",
)

check(
    integrated_location.doi == "10.1000/integrated",
    "integrated discovery retains normalised DOI",
)

check(
    integrated_location.pdf_url == "https://example.org/integrated.pdf",
    "integrated discovery retains OA PDF location",
)

check(
    integrated_location.landing_page_url
    == "https://example.org/integrated",
    "integrated discovery retains landing-page location",
)

check(
    integrated_location.source == "openalex",
    "integrated discovery retains OpenAlex provenance",
)


print("\n[10] substantive retrieval uses discovered source location only")

retrieval_calls = []


def fake_text_fetcher(url):
    retrieval_calls.append(url)
    return (
        "Synthetic scholarly article text containing substantive "
        "methods and results."
    )


retrieval_location = academic_claims.SourceLocation(
    status="location_found",
    doi="10.1000/retrieval",
    source="openalex",
    landing_page_url="https://example.org/article",
    pdf_url=None,
    is_oa=True,
    reasons=["Synthetic accessible source location."],
)

retrieved = academic_claims.retrieve_source_from_location(
    retrieval_location,
    fetcher=fake_text_fetcher,
)

check(
    retrieval_calls == ["https://example.org/article"],
    "retrieval fetcher receives discovered URL only",
)

check(
    retrieved.status == "retrieved",
    "successful substantive retrieval is explicit",
)

check(
    retrieved.doi == "10.1000/retrieval",
    "retrieved source retains bibliographic identifier",
)

check(
    retrieved.source == "openalex",
    "retrieved source retains discovery provenance",
)

check(
    retrieved.text is not None
    and "substantive methods and results" in retrieved.text,
    "retrieved substantive text remains inspectable",
)

check(
    retrieved.locator == "landing_page",
    "retrieval type is recorded explicitly",
)


print("\n[11] empty fetched content is not substantive retrieval")


def fake_empty_fetcher(url):
    return ""


empty_retrieval = academic_claims.retrieve_source_from_location(
    retrieval_location,
    fetcher=fake_empty_fetcher,
)

check(
    empty_retrieval.status == "not_retrieved",
    "empty fetched content is not reported as retrieved",
)

check(
    empty_retrieval.text is None,
    "empty fetched content does not create source text",
)

check(
    empty_retrieval.locator is None,
    "failed substantive retrieval does not claim a source locator",
)

check(
    any(
        "empty" in reason.lower()
        for reason in empty_retrieval.reasons
    ),
    "empty-content retrieval failure is explained",
)


print("\n[12] fetch failure remains an explicit retrieval failure")


def fake_failing_fetcher(url):
    raise academic_claims.SourceRetrievalError("HTTP 403")


try:
    failed_fetch = academic_claims.retrieve_source_from_location(
        retrieval_location,
        fetcher=fake_failing_fetcher,
    )
except RuntimeError:
    failed_fetch = None


check(
    failed_fetch is not None,
    "fetch failure is contained by retrieval layer",
)

check(
    failed_fetch is not None
    and failed_fetch.status == "not_retrieved",
    "fetch failure is represented as not retrieved",
)

check(
    failed_fetch is not None
    and failed_fetch.doi == "10.1000/retrieval",
    "fetch failure retains bibliographic identifier",
)

check(
    failed_fetch is not None
    and failed_fetch.source == "openalex",
    "fetch failure retains discovery provenance",
)

check(
    failed_fetch is not None
    and failed_fetch.text is None,
    "fetch failure does not invent source text",
)

check(
    failed_fetch is not None
    and failed_fetch.locator is None,
    "fetch failure does not claim successful retrieval locator",
)

check(
    failed_fetch is not None
    and any("failed" in reason.lower() for reason in failed_fetch.reasons),
    "fetch failure is explained explicitly",
)


print("\n[13] source without retrievable URL does not invoke fetcher")

no_url_calls = []


def should_not_be_called(url):
    no_url_calls.append(url)
    raise AssertionError("fetcher must not be called without a source URL")


no_url_location = academic_claims.SourceLocation(
    status="location_not_found",
    doi="10.1000/no-location",
    source="openalex",
    landing_page_url=None,
    pdf_url=None,
    is_oa=None,
    reasons=["OpenAlex supplied no accessible source location."],
)

no_url_retrieval = academic_claims.retrieve_source_from_location(
    no_url_location,
    fetcher=should_not_be_called,
)

check(
    no_url_calls == [],
    "missing source URL never invokes fetcher",
)

check(
    no_url_retrieval.status == "not_retrieved",
    "missing source URL remains not retrieved",
)

check(
    no_url_retrieval.doi == "10.1000/no-location",
    "missing source URL retains bibliographic identifier",
)

check(
    no_url_retrieval.source == "openalex",
    "missing source URL retains discovery provenance",
)

check(
    no_url_retrieval.text is None,
    "missing source URL does not invent source text",
)

check(
    no_url_retrieval.locator is None,
    "missing source URL does not invent retrieval locator",
)


print("\n[14] unexpected fetcher errors are not misclassified as retrieval failure")


def buggy_fetcher(url):
    raise TypeError("synthetic programming error")


unexpected_error_escaped = False

try:
    academic_claims.retrieve_source_from_location(
        retrieval_location,
        fetcher=buggy_fetcher,
    )
except TypeError:
    unexpected_error_escaped = True

check(
    unexpected_error_escaped,
    "unexpected programming error escapes retrieval-failure handling",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat claim-support contract checks passed.")
