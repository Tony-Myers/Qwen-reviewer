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


print("\n[15] downloaded source remains distinct from retrieved scholarly text")

downloaded = academic_claims.DownloadedSource(
    status="downloaded",
    requested_url="https://example.org/article",
    final_url="https://publisher.example.org/article",
    content_type="text/html; charset=utf-8",
    content=b"<html><body>Publisher page</body></html>",
    reasons=["Synthetic HTTP download."],
)

check(
    downloaded.status == "downloaded",
    "successful HTTP transfer has explicit downloaded status",
)

check(
    downloaded.requested_url == "https://example.org/article",
    "download preserves requested URL",
)

check(
    downloaded.final_url == "https://publisher.example.org/article",
    "download preserves final URL after redirect",
)

check(
    downloaded.content_type == "text/html; charset=utf-8",
    "download preserves response content type",
)

check(
    downloaded.content == b"<html><body>Publisher page</body></html>",
    "download preserves raw response bytes",
)

check(
    not hasattr(downloaded, "text"),
    "downloaded bytes are not prematurely represented as scholarly text",
)


print("\n[16] downloader rejects non-HTTP source URLs before network access")

unsafe_http_calls = []


def should_not_fetch_unsafe(url):
    unsafe_http_calls.append(url)
    raise AssertionError("HTTP client must not receive unsafe URL")


unsafe_urls = [
    "file:///etc/passwd",
    "ftp://example.org/article.pdf",
    "javascript:alert(1)",
    "/local/path/article.pdf",
    "not-a-url",
]

unsafe_results = []

for unsafe_url in unsafe_urls:
    try:
        result = academic_claims.safe_http_fetch(
            unsafe_url,
            http_get=should_not_fetch_unsafe,
        )
    except academic_claims.SourceRetrievalError:
        unsafe_results.append(True)
    else:
        unsafe_results.append(False)

check(
    all(unsafe_results),
    "non-HTTP source URLs are rejected as retrieval errors",
)

check(
    unsafe_http_calls == [],
    "unsafe source URLs never reach HTTP client",
)


print("\n[17] eligible HTTP source URLs reach downloader unchanged")

eligible_http_calls = []


def fake_http_get(url):
    eligible_http_calls.append(url)
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url=url,
        content_type="application/pdf",
        content=b"%PDF-synthetic",
        reasons=["Synthetic successful HTTP response."],
    )


https_download = academic_claims.safe_http_fetch(
    "https://example.org/article.pdf",
    http_get=fake_http_get,
)

http_download = academic_claims.safe_http_fetch(
    "http://example.org/article.pdf",
    http_get=fake_http_get,
)

check(
    eligible_http_calls == [
        "https://example.org/article.pdf",
        "http://example.org/article.pdf",
    ],
    "eligible HTTP(S) URLs reach HTTP client unchanged",
)

check(
    https_download.status == "downloaded",
    "eligible HTTPS source returns downloaded resource",
)

check(
    https_download.content_type == "application/pdf",
    "download preserves HTTP content type",
)

check(
    https_download.content == b"%PDF-synthetic",
    "download preserves raw HTTP bytes",
)

check(
    http_download.requested_url == "http://example.org/article.pdf",
    "eligible HTTP source remains supported",
)


print("\n[18] downloader rejects ineligible final URL after redirect")


def fake_unsafe_redirect(url):
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url="file:///etc/passwd",
        content_type="text/plain",
        content=b"synthetic unsafe redirect content",
        reasons=["Synthetic redirect."],
    )


unsafe_redirect_rejected = False

try:
    academic_claims.safe_http_fetch(
        "https://example.org/article",
        http_get=fake_unsafe_redirect,
    )
except academic_claims.SourceRetrievalError:
    unsafe_redirect_rejected = True

check(
    unsafe_redirect_rejected,
    "ineligible final URL is rejected after HTTP delegation",
)


print("\n[19] downloader rejects local and non-public network destinations")

blocked_network_calls = []


def should_not_fetch_local(url):
    blocked_network_calls.append(url)
    raise AssertionError("HTTP client must not receive local/private URL")


blocked_urls = [
    "http://localhost/article",
    "http://127.0.0.1/article",
    "http://127.1/article",
    "http://0.0.0.0/article",
    "http://[::1]/article",
    "http://169.254.169.254/article",
    "http://10.0.0.1/article",
    "http://172.16.0.1/article",
    "http://192.168.1.1/article",
]

blocked_results = []

for blocked_url in blocked_urls:
    try:
        academic_claims.safe_http_fetch(
            blocked_url,
            http_get=should_not_fetch_local,
        )
    except academic_claims.SourceRetrievalError:
        blocked_results.append(True)
    else:
        blocked_results.append(False)

check(
    all(blocked_results),
    "local/private source destinations are rejected",
)

check(
    blocked_network_calls == [],
    "local/private destinations never reach HTTP client",
)


print("\n[20] downloader rejects hostname resolving to non-public address")

dns_http_calls = []
dns_resolver_calls = []


def fake_private_resolver(hostname):
    dns_resolver_calls.append(hostname)
    return ["10.23.45.67"]


def should_not_fetch_private_dns(url):
    dns_http_calls.append(url)
    raise AssertionError("HTTP client must not receive privately resolved hostname")


private_dns_rejected = False

try:
    academic_claims.safe_http_fetch(
        "https://apparently-public.example/article",
        http_get=should_not_fetch_private_dns,
        resolver=fake_private_resolver,
    )
except academic_claims.SourceRetrievalError:
    private_dns_rejected = True

check(
    dns_resolver_calls == ["apparently-public.example"],
    "hostname is resolved before HTTP delegation",
)

check(
    private_dns_rejected,
    "hostname resolving to non-public address is rejected",
)

check(
    dns_http_calls == [],
    "privately resolved hostname never reaches HTTP client",
)


print("\n[21] DNS policy requires every resolved address to be public")

public_http_calls = []
mixed_http_calls = []


def fake_public_resolver(hostname):
    return ["8.8.8.8", "1.1.1.1"]


def fake_public_http_get(url):
    public_http_calls.append(url)
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url=url,
        content_type="text/html",
        content=b"<html>synthetic public source</html>",
        reasons=["Synthetic public download."],
    )


public_download = academic_claims.safe_http_fetch(
    "https://public-source.example/article",
    http_get=fake_public_http_get,
    resolver=fake_public_resolver,
)

check(
    public_http_calls == ["https://public-source.example/article"],
    "hostname resolving only to public addresses reaches HTTP client",
)

check(
    public_download.status == "downloaded",
    "public-only DNS resolution permits download",
)


def fake_mixed_resolver(hostname):
    return ["8.8.8.8", "10.0.0.4"]


def should_not_fetch_mixed(url):
    mixed_http_calls.append(url)
    raise AssertionError("mixed public/private resolution must not reach HTTP client")


mixed_resolution_rejected = False

try:
    academic_claims.safe_http_fetch(
        "https://mixed-source.example/article",
        http_get=should_not_fetch_mixed,
        resolver=fake_mixed_resolver,
    )
except academic_claims.SourceRetrievalError:
    mixed_resolution_rejected = True

check(
    mixed_resolution_rejected,
    "mixed public/private DNS resolution is rejected",
)

check(
    mixed_http_calls == [],
    "mixed DNS resolution never reaches HTTP client",
)


print("\n[22] connection boundary receives validated network destination")

connection_calls = []


def fake_connection_adapter(url, hostname, validated_addresses):
    connection_calls.append(
        (url, hostname, tuple(validated_addresses))
    )
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url=url,
        content_type="application/pdf",
        content=b"%PDF-synthetic",
        reasons=["Synthetic validated-address connection."],
    )


connected = academic_claims.fetch_validated_http_source(
    "https://journal.example/article.pdf",
    hostname="journal.example",
    validated_addresses=["8.8.8.8", "1.1.1.1"],
    connection_adapter=fake_connection_adapter,
)

check(
    connection_calls == [
        (
            "https://journal.example/article.pdf",
            "journal.example",
            ("8.8.8.8", "1.1.1.1"),
        )
    ],
    "connection adapter receives URL, hostname, and validated addresses",
)

check(
    connected.status == "downloaded",
    "validated connection returns downloaded resource",
)

check(
    connected.content == b"%PDF-synthetic",
    "validated connection preserves downloaded bytes",
)


print("\n[23] connection boundary independently rejects non-public addresses")

direct_connection_calls = []


def should_not_connect_non_public(url, hostname, validated_addresses):
    direct_connection_calls.append(
        (url, hostname, tuple(validated_addresses))
    )
    raise AssertionError("non-public destination must not reach connection adapter")


non_public_connection_rejected = False

try:
    academic_claims.fetch_validated_http_source(
        "https://journal.example/article.pdf",
        hostname="journal.example",
        validated_addresses=["8.8.8.8", "10.0.0.7"],
        connection_adapter=should_not_connect_non_public,
    )
except academic_claims.SourceRetrievalError:
    non_public_connection_rejected = True

check(
    non_public_connection_rejected,
    "connection boundary rejects mixed public/private addresses",
)

check(
    direct_connection_calls == [],
    "non-public address never reaches connection adapter",
)

if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll Academic Chat claim-support contract checks passed.")

print("\n[24] pinned network backend delegates validated IP to httpcore")

import httpcore

resolved_hosts = []
parent_calls = []
sentinel_stream = object()

original_connect_tcp = httpcore.SyncBackend.connect_tcp

def fake_parent_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    parent_calls.append(
        {
            "host": host,
            "port": port,
            "timeout": timeout,
            "local_address": local_address,
            "socket_options": socket_options,
        }
    )
    return sentinel_stream

def fake_resolver(hostname):
    resolved_hosts.append(hostname)
    return ["8.8.8.8"]

httpcore.SyncBackend.connect_tcp = fake_parent_connect_tcp

try:
    backend = academic_claims.PinnedSyncBackend(
        resolver=fake_resolver,
    )

    stream = backend.connect_tcp(
        host="journal.example",
        port=443,
        timeout=5.0,
        local_address=None,
        socket_options=[(6, 1, 1)],
    )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp

assert resolved_hosts == ["journal.example"]
assert parent_calls == [
    {
        "host": "8.8.8.8",
        "port": 443,
        "timeout": 5.0,
        "local_address": None,
        "socket_options": [(6, 1, 1)],
    }
]
assert stream is sentinel_stream

print("PASS: hostname is resolved exactly once by pinned backend")
print("PASS: httpcore receives validated IP rather than hostname")
print("PASS: connection arguments are preserved")

print("\n[25] pinned network backend rejects mixed public/private DNS results")

mixed_parent_calls = []

def mixed_resolver(hostname):
    assert hostname == "journal.example"
    return ["8.8.8.8", "10.0.0.7"]

original_connect_tcp = httpcore.SyncBackend.connect_tcp

def forbidden_parent_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    mixed_parent_calls.append(host)
    raise AssertionError(
        "httpcore parent backend must not receive mixed DNS results."
    )

httpcore.SyncBackend.connect_tcp = forbidden_parent_connect_tcp

try:
    mixed_backend = academic_claims.PinnedSyncBackend(
        resolver=mixed_resolver,
    )

    try:
        mixed_backend.connect_tcp(
            host="journal.example",
            port=443,
            timeout=5.0,
        )
    except academic_claims.SourceRetrievalError:
        pass
    else:
        raise AssertionError(
            "Mixed public/private DNS results must be rejected."
        )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp

assert mixed_parent_calls == []

print("PASS: pinned backend rejects mixed public/private DNS results")
print("PASS: rejected DNS result never reaches httpcore connection backend")

print("\n[26] httpcore preserves original hostname for TLS authentication")

connection_hosts = []
tls_hostnames = []

class RecordingStream(httpcore.NetworkStream):
    def read(self, max_bytes, timeout=None):
        return b""

    def write(self, buffer, timeout=None):
        pass

    def close(self):
        pass

    def start_tls(
        self,
        ssl_context,
        server_hostname=None,
        timeout=None,
    ):
        tls_hostnames.append(server_hostname)
        return self

    def get_extra_info(self, info):
        return None

class RecordingBackend(httpcore.NetworkBackend):
    def connect_tcp(
        self,
        host,
        port,
        timeout=None,
        local_address=None,
        socket_options=None,
    ):
        connection_hosts.append(host)
        return RecordingStream()

    def connect_unix_socket(
        self,
        path,
        timeout=None,
        socket_options=None,
    ):
        raise AssertionError("Unix socket must not be used.")

    def sleep(self, seconds):
        pass

origin = httpcore.Origin(
    scheme=b"https",
    host=b"journal.example",
    port=443,
)

connection = httpcore.HTTPConnection(
    origin=origin,
    network_backend=RecordingBackend(),
    http1=True,
    http2=False,
)

request = httpcore.Request(
    method="GET",
    url="https://journal.example/article.pdf",
)

try:
    connection.handle_request(request)
except Exception:
    # The synthetic stream does not implement an HTTP response.
    # We only need connection and TLS setup for this contract.
    pass

assert connection_hosts == ["journal.example"]
assert tls_hostnames == ["journal.example"]

print("PASS: httpcore sends original origin hostname to network backend")
print("PASS: httpcore preserves original hostname as TLS server_hostname")

print("\n[27] redirect destination is validated before the next request")

redirect_requests = []

def redirect_requester(url):
    redirect_requests.append(url)

    if len(redirect_requests) == 1:
        return {
            "status_code": 302,
            "location": "http://127.0.0.1/private",
            "content_type": "text/html",
            "content": b"",
        }

    raise AssertionError(
        "Unsafe redirect destination must never receive a request."
    )

try:
    academic_claims.fetch_with_validated_redirects(
        "https://journal.example/article",
        requester=redirect_requester,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Redirect to non-public destination must be rejected."
    )

assert redirect_requests == [
    "https://journal.example/article"
]

print("PASS: initial eligible source is requested")
print("PASS: unsafe redirect is rejected before a second request")

print("\n[28] redirect hostname is resolved and validated before next request")

dns_redirect_requests = []
dns_redirect_resolutions = []

def dns_redirect_requester(url):
    dns_redirect_requests.append(url)

    if len(dns_redirect_requests) == 1:
        return {
            "status_code": 302,
            "location": "https://redirect.example/private",
            "content_type": "text/html",
            "content": b"",
        }

    raise AssertionError(
        "Privately resolved redirect destination must never receive a request."
    )

def dns_redirect_resolver(hostname):
    dns_redirect_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8"]

    if hostname == "redirect.example":
        return ["10.0.0.7"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

try:
    academic_claims.fetch_with_validated_redirects(
        "https://journal.example/article",
        requester=dns_redirect_requester,
        resolver=dns_redirect_resolver,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Redirect hostname resolving privately must be rejected."
    )

assert dns_redirect_requests == [
    "https://journal.example/article"
]

assert dns_redirect_resolutions == [
    "journal.example",
    "redirect.example",
]

print("PASS: initial hostname is resolved and validated")
print("PASS: redirect hostname is resolved before second request")
print("PASS: privately resolved redirect never reaches requester")

print("\n[29] safe relative redirect is resolved once per requested hop")

relative_redirect_requests = []
relative_redirect_resolutions = []

def relative_redirect_requester(url):
    relative_redirect_requests.append(url)

    if url == "https://journal.example/articles/123":
        return {
            "status_code": 302,
            "location": "../pdf/123.pdf",
            "content_type": "text/html",
            "content": b"",
        }

    if url == "https://journal.example/pdf/123.pdf":
        return {
            "status_code": 200,
            "location": None,
            "content_type": "application/pdf",
            "content": b"%PDF-test",
        }

    raise AssertionError(f"Unexpected request URL: {url}")

def relative_redirect_resolver(hostname):
    relative_redirect_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

relative_result = academic_claims.fetch_with_validated_redirects(
    "https://journal.example/articles/123",
    requester=relative_redirect_requester,
    resolver=relative_redirect_resolver,
)

assert relative_redirect_requests == [
    "https://journal.example/articles/123",
    "https://journal.example/pdf/123.pdf",
]

assert relative_redirect_resolutions == [
    "journal.example",
    "journal.example",
]

assert relative_result["status_code"] == 200
assert relative_result["content_type"] == "application/pdf"
assert relative_result["content"] == b"%PDF-test"

print("PASS: relative redirect is resolved against current URL")
print("PASS: both eligible URLs are requested in order")
print("PASS: each requested hop is resolved and validated exactly once")
print("PASS: final non-redirect response is returned")

print("\n[30] redirect limit is enforced before another request")

limit_requests = []
limit_resolutions = []

def limit_requester(url):
    limit_requests.append(url)

    hop = len(limit_requests)

    return {
        "status_code": 302,
        "location": f"/hop-{hop}",
        "content_type": "text/html",
        "content": b"",
    }

def limit_resolver(hostname):
    limit_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

try:
    academic_claims.fetch_with_validated_redirects(
        "https://journal.example/start",
        requester=limit_requester,
        resolver=limit_resolver,
        max_redirects=2,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Redirect chain beyond configured limit must be rejected."
    )

assert limit_requests == [
    "https://journal.example/start",
    "https://journal.example/hop-1",
    "https://journal.example/hop-2",
]

assert limit_resolutions == [
    "journal.example",
    "journal.example",
    "journal.example",
]

print("PASS: configured number of redirects is permitted")
print("PASS: redirect beyond configured limit is rejected")
print("PASS: no request is made beyond redirect limit")

print("\n[31] validated-address backend performs no DNS resolution")

parent_connection_calls = []

original_parent_connect_tcp = httpcore.SyncBackend.connect_tcp

def recording_parent_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    parent_connection_calls.append(
        {
            "host": host,
            "port": port,
            "timeout": timeout,
            "local_address": local_address,
            "socket_options": socket_options,
        }
    )
    return "validated-stream"

httpcore.SyncBackend.connect_tcp = recording_parent_connect_tcp

try:
    backend = academic_claims.ValidatedAddressSyncBackend(
        validated_addresses=["8.8.8.8"]
    )

    stream = backend.connect_tcp(
        host="journal.example",
        port=443,
        timeout=5.0,
        local_address=None,
        socket_options=[(6, 1, 1)],
    )
finally:
    httpcore.SyncBackend.connect_tcp = original_parent_connect_tcp

assert stream == "validated-stream"

assert parent_connection_calls == [
    {
        "host": "8.8.8.8",
        "port": 443,
        "timeout": 5.0,
        "local_address": None,
        "socket_options": [(6, 1, 1)],
    }
]

print("PASS: validated-address backend requires no resolver")
print("PASS: original hostname is never delegated for TCP resolution")
print("PASS: supplied validated IP is the TCP destination")

print("\n[32] URL validation returns the exact approved network destination")

destination_resolutions = []

def destination_resolver(hostname):
    destination_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8", "1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

destination = academic_claims.resolve_validated_http_destination(
    "https://Journal.Example./article.pdf",
    resolver=destination_resolver,
)

assert destination.hostname == "journal.example"
assert destination.addresses == ["8.8.8.8", "1.1.1.1"]
assert destination_resolutions == ["journal.example"]

print("PASS: URL hostname is normalised")
print("PASS: hostname is resolved exactly once")
print("PASS: validated addresses are retained rather than discarded")

print("\n[33] one DNS resolution supplies the validated connection boundary")

join_resolutions = []
join_connections = []

def join_resolver(hostname):
    join_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8", "1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

def join_connection_adapter(url, hostname, validated_addresses):
    join_connections.append(
        {
            "url": url,
            "hostname": hostname,
            "validated_addresses": list(validated_addresses),
        }
    )

    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url=url,
        content_type="application/pdf",
        content=b"source-content",
        reasons=[],
    )

join_url = "https://journal.example/article.pdf"

join_destination = academic_claims.resolve_validated_http_destination(
    join_url,
    resolver=join_resolver,
)

join_downloaded = academic_claims.fetch_validated_http_source(
    join_url,
    hostname=join_destination.hostname,
    validated_addresses=join_destination.addresses,
    connection_adapter=join_connection_adapter,
)

assert join_resolutions == ["journal.example"]

assert join_connections == [
    {
        "url": "https://journal.example/article.pdf",
        "hostname": "journal.example",
        "validated_addresses": ["8.8.8.8", "1.1.1.1"],
    }
]

assert join_downloaded.content == b"source-content"
assert join_downloaded.content_type == "application/pdf"
assert join_downloaded.final_url == join_url

print("PASS: hostname is resolved exactly once")
print("PASS: exact validated addresses reach the connection boundary")
print("PASS: connection boundary performs no additional DNS resolution")
print("PASS: downloaded source is returned unchanged")

print("\n[34] redirect controller passes its validated destination to requester")

aware_resolutions = []
aware_requests = []

def aware_resolver(hostname):
    aware_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8"]

    if hostname == "cdn.example":
        return ["1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

def aware_requester(url, destination):
    aware_requests.append(
        {
            "url": url,
            "hostname": destination.hostname,
            "addresses": list(destination.addresses),
        }
    )

    if url == "https://journal.example/article":
        return academic_claims.HTTPHopResponse(
            status_code=302,
            location="https://cdn.example/article.pdf",
            content_type=None,
            content=b"",
        )

    if url == "https://cdn.example/article.pdf":
        return academic_claims.HTTPHopResponse(
            status_code=200,
            location=None,
            content_type=None,
            content=b"",
        )

    raise AssertionError(f"Unexpected URL: {url}")

aware_response = academic_claims.fetch_with_validated_destinations(
    "https://journal.example/article",
    requester=aware_requester,
    resolver=aware_resolver,
)

assert aware_resolutions == [
    "journal.example",
    "cdn.example",
]

assert aware_requests == [
    {
        "url": "https://journal.example/article",
        "hostname": "journal.example",
        "addresses": ["8.8.8.8"],
    },
    {
        "url": "https://cdn.example/article.pdf",
        "hostname": "cdn.example",
        "addresses": ["1.1.1.1"],
    },
]

assert aware_response.status_code == 200

print("PASS: each redirect hop is resolved exactly once")
print("PASS: requester receives the destination validated for that hop")
print("PASS: redirected host receives its own validated destination")

print("\n[35] validated-address backend pins TCP while preserving TLS hostname")

validated_origin_hosts = []
validated_tcp_hosts = []
validated_tls_hostnames = []

class ValidatedRecordingStream(httpcore.NetworkStream):
    def read(self, max_bytes, timeout=None):
        return b""

    def write(self, buffer, timeout=None):
        pass

    def close(self):
        pass

    def start_tls(
        self,
        ssl_context,
        server_hostname=None,
        timeout=None,
    ):
        validated_tls_hostnames.append(server_hostname)
        return self

    def get_extra_info(self, info):
        return None

original_validated_parent_connect_tcp = httpcore.SyncBackend.connect_tcp

def validated_recording_parent_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    validated_tcp_hosts.append(host)
    return ValidatedRecordingStream()

httpcore.SyncBackend.connect_tcp = validated_recording_parent_connect_tcp

try:
    validated_backend = academic_claims.ValidatedAddressSyncBackend(
        validated_addresses=["8.8.8.8"]
    )

    original_backend_connect_tcp = validated_backend.connect_tcp

    def recording_validated_connect_tcp(
        host,
        port,
        timeout=None,
        local_address=None,
        socket_options=None,
    ):
        validated_origin_hosts.append(host)
        return original_backend_connect_tcp(
            host=host,
            port=port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    validated_backend.connect_tcp = recording_validated_connect_tcp

    validated_origin = httpcore.Origin(
        scheme=b"https",
        host=b"journal.example",
        port=443,
    )

    validated_connection = httpcore.HTTPConnection(
        origin=validated_origin,
        network_backend=validated_backend,
        http1=True,
        http2=False,
    )

    validated_request = httpcore.Request(
        method="GET",
        url="https://journal.example/article.pdf",
    )

    try:
        validated_connection.handle_request(validated_request)
    except Exception:
        # The synthetic stream does not implement an HTTP response.
        # We only need origin, TCP destination, and TLS setup.
        pass
finally:
    httpcore.SyncBackend.connect_tcp = original_validated_parent_connect_tcp

assert validated_origin_hosts == ["journal.example"]
assert validated_tcp_hosts == ["8.8.8.8"]
assert validated_tls_hostnames == ["journal.example"]

print("PASS: httpcore presents original hostname to validated backend")
print("PASS: TCP connection is pinned to validated numeric IP")
print("PASS: TLS authentication retains original hostname")

print("\n[36] HTTP hop response preserves redirect and payload metadata")

hop = academic_claims.HTTPHopResponse(
    status_code=302,
    location="../article.pdf",
    content_type="text/html; charset=utf-8",
    content=b"redirect body",
)

assert hop.status_code == 302
assert hop.location == "../article.pdf"
assert hop.content_type == "text/html; charset=utf-8"
assert hop.content == b"redirect body"

print("PASS: hop status is retained")
print("PASS: redirect location is retained")
print("PASS: content type is retained")
print("PASS: response bytes are retained")

print("\n[37] validated single-hop requester builds and translates HTTP request")

single_hop_connections = []
single_hop_requests = []

class FakeHopResponse:
    status = 302
    headers = [
        (b"location", b"../article.pdf"),
        (b"content-type", b"text/html; charset=utf-8"),
    ]

    def iter_stream(self):
        yield b"redirect-body"

    def close(self):
        pass

class FakeHopConnection:
    def handle_request(self, request):
        single_hop_requests.append(request)
        return FakeHopResponse()

    def close(self):
        pass

def fake_connection_factory(origin, network_backend, http1, http2):
    single_hop_connections.append(
        {
            "origin": origin,
            "network_backend": network_backend,
            "http1": http1,
            "http2": http2,
        }
    )
    return FakeHopConnection()

single_hop_destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

single_hop_response = academic_claims.request_validated_http_hop(
    "https://journal.example/articles/123?download=1",
    destination=single_hop_destination,
    connection_factory=fake_connection_factory,
)

assert len(single_hop_connections) == 1

single_hop_connection = single_hop_connections[0]

assert single_hop_connection["origin"] == httpcore.Origin(
    scheme=b"https",
    host=b"journal.example",
    port=443,
)

assert isinstance(
    single_hop_connection["network_backend"],
    academic_claims.ValidatedAddressSyncBackend,
)

assert single_hop_connection["http1"] is True
assert single_hop_connection["http2"] is False

assert len(single_hop_requests) == 1

single_hop_request = single_hop_requests[0]

assert single_hop_request.method == b"GET"
assert single_hop_request.url.scheme == b"https"
assert single_hop_request.url.host == b"journal.example"
assert single_hop_request.url.port is None
assert single_hop_request.url.target == b"/articles/123?download=1"

assert single_hop_response == academic_claims.HTTPHopResponse(
    status_code=302,
    location="../article.pdf",
    content_type="text/html; charset=utf-8",
    content=b"redirect-body",
)

print("PASS: original HTTP origin is retained")
print("PASS: validated-address backend is installed")
print("PASS: requester issues exactly one GET with path and query")
print("PASS: requester does not follow redirect itself")
print("PASS: response headers and bytes become HTTPHopResponse")

print("\n[38] single-hop requester enforces maximum body size while streaming")

bounded_response_closed = []
bounded_connection_closed = []

class OversizedHopResponse:
    status = 200
    headers = [
        (b"content-type", b"application/pdf"),
    ]

    def iter_stream(self):
        yield b"12345"
        yield b"67890"
        yield b"X"

    def close(self):
        bounded_response_closed.append(True)

class OversizedHopConnection:
    def handle_request(self, request):
        return OversizedHopResponse()

    def close(self):
        bounded_connection_closed.append(True)

def oversized_connection_factory(origin, network_backend, http1, http2):
    return OversizedHopConnection()

oversized_destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

try:
    academic_claims.request_validated_http_hop(
        "https://journal.example/article.pdf",
        destination=oversized_destination,
        connection_factory=oversized_connection_factory,
        max_bytes=10,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Response exceeding maximum body size must be rejected."
    )

assert bounded_response_closed == [True]
assert bounded_connection_closed == [True]

print("PASS: body larger than configured maximum is rejected")
print("PASS: oversized response is closed")
print("PASS: connection is closed after oversized response")

print("\n[39] response exactly at maximum body size is accepted")

exact_response_closed = []
exact_connection_closed = []

class ExactLimitHopResponse:
    status = 200
    headers = [
        (b"content-type", b"application/pdf"),
    ]

    def iter_stream(self):
        yield b"12345"
        yield b"67890"

    def close(self):
        exact_response_closed.append(True)

class ExactLimitHopConnection:
    def handle_request(self, request):
        return ExactLimitHopResponse()

    def close(self):
        exact_connection_closed.append(True)

def exact_limit_connection_factory(origin, network_backend, http1, http2):
    return ExactLimitHopConnection()

exact_limit_destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

exact_limit_response = academic_claims.request_validated_http_hop(
    "https://journal.example/article.pdf",
    destination=exact_limit_destination,
    connection_factory=exact_limit_connection_factory,
    max_bytes=10,
)

assert exact_limit_response.status_code == 200
assert exact_limit_response.content == b"1234567890"
assert exact_response_closed == [True]
assert exact_connection_closed == [True]

print("PASS: body exactly equal to configured maximum is accepted")
print("PASS: complete body is retained")
print("PASS: response and connection are closed after success")

print("\n[40] destination-aware redirect controller accepts typed HTTP hop responses")

typed_redirect_requests = []
typed_redirect_resolutions = []

def typed_redirect_resolver(hostname):
    typed_redirect_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8"]

    if hostname == "cdn.example":
        return ["1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

def typed_redirect_requester(url, destination):
    typed_redirect_requests.append(
        (
            url,
            destination.hostname,
            list(destination.addresses),
        )
    )

    if url == "https://journal.example/article":
        return academic_claims.HTTPHopResponse(
            status_code=302,
            location="https://cdn.example/article.pdf",
            content_type="text/html",
            content=b"",
        )

    if url == "https://cdn.example/article.pdf":
        return academic_claims.HTTPHopResponse(
            status_code=200,
            location=None,
            content_type="application/pdf",
            content=b"pdf-content",
        )

    raise AssertionError(f"Unexpected URL: {url}")

typed_redirect_response = academic_claims.fetch_with_validated_destinations(
    "https://journal.example/article",
    requester=typed_redirect_requester,
    resolver=typed_redirect_resolver,
)

assert typed_redirect_response.status_code == 200
assert typed_redirect_response.content_type == "application/pdf"
assert typed_redirect_response.content == b"pdf-content"

assert typed_redirect_resolutions == [
    "journal.example",
    "cdn.example",
]

assert typed_redirect_requests == [
    (
        "https://journal.example/article",
        "journal.example",
        ["8.8.8.8"],
    ),
    (
        "https://cdn.example/article.pdf",
        "cdn.example",
        ["1.1.1.1"],
    ),
]

print("PASS: typed redirect response is consumed by controller")
print("PASS: redirect destination is independently resolved and validated")
print("PASS: final typed HTTP response is returned unchanged")

print("\n[41] redirect controller composes with real validated single-hop requester")

composed_resolutions = []
composed_connections = []
composed_requests = []

def composed_resolver(hostname):
    composed_resolutions.append(hostname)

    if hostname == "journal.example":
        return ["8.8.8.8"]

    if hostname == "cdn.example":
        return ["1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")

class ComposedHopResponse:
    def __init__(self, status, headers, content):
        self.status = status
        self.headers = headers
        self._content = content

    def iter_stream(self):
        yield self._content

    def close(self):
        pass

class ComposedHopConnection:
    def __init__(self, origin, network_backend, http1, http2):
        self.origin = origin
        self.network_backend = network_backend
        composed_connections.append(
            {
                "host": origin.host.decode("ascii"),
                "addresses": list(network_backend._validated_addresses),
            }
        )

    def handle_request(self, request):
        scheme = request.url.scheme.decode("ascii")
        host = request.url.host.decode("ascii")
        port = request.url.port
        target = request.url.target.decode("ascii")

        default_port = (
            (scheme == "https" and port in {None, 443})
            or (scheme == "http" and port in {None, 80})
        )
        authority = host if default_port else f"{host}:{port}"
        url = f"{scheme}://{authority}{target}"

        composed_requests.append(url)

        if url == "https://journal.example/article":
            return ComposedHopResponse(
                status=302,
                headers=[
                    (
                        b"location",
                        b"https://cdn.example/article.pdf",
                    ),
                    (b"content-type", b"text/html"),
                ],
                content=b"",
            )

        if url == "https://cdn.example/article.pdf":
            return ComposedHopResponse(
                status=200,
                headers=[
                    (b"content-type", b"application/pdf"),
                ],
                content=b"pdf-content",
            )

        raise AssertionError(f"Unexpected request URL: {url}")

    def close(self):
        pass

def composed_requester(url, destination):
    return academic_claims.request_validated_http_hop(
        url,
        destination=destination,
        connection_factory=ComposedHopConnection,
        max_bytes=1024,
    )

composed_response = academic_claims.fetch_with_validated_destinations(
    "https://journal.example/article",
    requester=composed_requester,
    resolver=composed_resolver,
)

assert composed_response.status_code == 200
assert composed_response.content_type == "application/pdf"
assert composed_response.content == b"pdf-content"

assert composed_resolutions == [
    "journal.example",
    "cdn.example",
]

assert composed_connections == [
    {
        "host": "journal.example",
        "addresses": ["8.8.8.8"],
    },
    {
        "host": "cdn.example",
        "addresses": ["1.1.1.1"],
    },
]

assert composed_requests == [
    "https://journal.example/article",
    "https://cdn.example/article.pdf",
]

print("PASS: redirect controller invokes real validated single-hop requester")
print("PASS: each hop retains its original hostname")
print("PASS: each hop receives only its separately validated address")
print("PASS: redirect is followed through typed HTTPHopResponse")
print("PASS: final PDF response survives the complete composed path")

print("\n[42] single-hop requester rejects URL and validated-destination mismatch")

mismatch_connections = []

def mismatch_connection_factory(origin, network_backend, http1, http2):
    mismatch_connections.append(True)
    raise AssertionError(
        "Connection factory must not be reached for mismatched destination."
    )

mismatched_destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

try:
    academic_claims.request_validated_http_hop(
        "https://other.example/article.pdf",
        destination=mismatched_destination,
        connection_factory=mismatch_connection_factory,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "URL hostname differing from validated destination must be rejected."
    )

assert mismatch_connections == []

print("PASS: URL/destination hostname mismatch is rejected")
print("PASS: mismatch is rejected before connection construction")

print("\n[43] equivalent canonical hostname forms remain accepted")

canonical_connections = []

class CanonicalHopResponse:
    status = 200
    headers = [
        (b"content-type", b"application/pdf"),
    ]

    def iter_stream(self):
        yield b"pdf-content"

    def close(self):
        pass

class CanonicalHopConnection:
    def __init__(self, origin, network_backend, http1, http2):
        canonical_connections.append(
            {
                "host": origin.host.decode("ascii"),
                "addresses": list(network_backend._validated_addresses),
            }
        )

    def handle_request(self, request):
        return CanonicalHopResponse()

    def close(self):
        pass

canonical_destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

canonical_response = academic_claims.request_validated_http_hop(
    "https://Journal.Example./article.pdf",
    destination=canonical_destination,
    connection_factory=CanonicalHopConnection,
)

assert canonical_response.status_code == 200
assert canonical_response.content == b"pdf-content"
assert canonical_connections == [
    {
        "host": "journal.example",
        "addresses": ["8.8.8.8"],
    }
]

print("PASS: hostname comparison tolerates case and trailing root dot")
print("PASS: canonical validated hostname remains the HTTP/TLS origin")
print("PASS: validated address remains the only TCP destination")

print("\n[44] source URLs with embedded credentials are rejected before resolution")

credential_resolutions = []

def credential_resolver(hostname):
    credential_resolutions.append(hostname)
    return ["8.8.8.8"]

credential_urls = [
    "https://user@journal.example/article",
    "https://user:password@journal.example/article",
]

for credential_url in credential_urls:
    try:
        academic_claims.resolve_validated_http_destination(
            credential_url,
            resolver=credential_resolver,
        )
    except academic_claims.SourceRetrievalError:
        pass
    else:
        raise AssertionError(
            f"Credential-bearing source URL must be rejected: {credential_url}"
        )

assert credential_resolutions == []

print("PASS: username-bearing source URL is rejected")
print("PASS: username/password source URL is rejected")
print("PASS: credential-bearing URLs are rejected before DNS resolution")

print("\n[45] malformed source URL ports are rejected before resolution")

malformed_port_resolutions = []

def malformed_port_resolver(hostname):
    malformed_port_resolutions.append(hostname)
    return ["8.8.8.8"]

malformed_port_urls = [
    "https://journal.example:abc/article",
    "https://journal.example:99999/article",
]

for malformed_port_url in malformed_port_urls:
    try:
        academic_claims.resolve_validated_http_destination(
            malformed_port_url,
            resolver=malformed_port_resolver,
        )
    except academic_claims.SourceRetrievalError:
        pass
    else:
        raise AssertionError(
            f"Malformed source URL port must be rejected: {malformed_port_url}"
        )

assert malformed_port_resolutions == []

print("PASS: non-numeric source URL port is rejected")
print("PASS: out-of-range source URL port is rejected")
print("PASS: malformed ports are rejected before DNS resolution")

print("\n[46] valid non-default source URL ports remain permitted")

nondefault_port_resolutions = []

def nondefault_port_resolver(hostname):
    nondefault_port_resolutions.append(hostname)
    return ["8.8.8.8"]

nondefault_destination = academic_claims.resolve_validated_http_destination(
    "https://journal.example:8443/article",
    resolver=nondefault_port_resolver,
)

assert nondefault_destination.hostname == "journal.example"
assert nondefault_destination.addresses == ["8.8.8.8"]
assert nondefault_port_resolutions == ["journal.example"]

print("PASS: valid non-default HTTPS port is accepted")
print("PASS: hostname is resolved normally for valid non-default port")
print("PASS: validated destination retains the approved network address")

print("\n[47] validated HTTP download preserves requested and final source URLs")

download_resolutions = []
download_requests = []

def download_resolver(hostname):
    download_resolutions.append(hostname)
    if hostname == "journal.example":
        return ["8.8.8.8"]
    if hostname == "cdn.example":
        return ["1.1.1.1"]
    raise AssertionError(f"Unexpected hostname: {hostname}")

def download_requester(url, destination):
    download_requests.append(
        (url, destination.hostname, list(destination.addresses))
    )

    if url == "https://journal.example/article":
        return academic_claims.HTTPHopResponse(
            status_code=302,
            location="https://cdn.example/article.pdf",
            content_type="text/html",
            content=b"",
        )

    if url == "https://cdn.example/article.pdf":
        return academic_claims.HTTPHopResponse(
            status_code=200,
            location=None,
            content_type="application/pdf",
            content=b"pdf-content",
        )

    raise AssertionError(f"Unexpected URL: {url}")

downloaded = academic_claims.download_validated_http_source(
    "https://journal.example/article",
    requester=download_requester,
    resolver=download_resolver,
)

assert isinstance(downloaded, academic_claims.DownloadedSource)
assert downloaded.status == "downloaded"
assert downloaded.requested_url == "https://journal.example/article"
assert downloaded.final_url == "https://cdn.example/article.pdf"
assert downloaded.content_type == "application/pdf"
assert downloaded.content == b"pdf-content"

assert download_resolutions == [
    "journal.example",
    "cdn.example",
]

assert download_requests == [
    (
        "https://journal.example/article",
        "journal.example",
        ["8.8.8.8"],
    ),
    (
        "https://cdn.example/article.pdf",
        "cdn.example",
        ["1.1.1.1"],
    ),
]

print("PASS: secure download returns DownloadedSource")
print("PASS: original requested URL is preserved")
print("PASS: final redirected URL is preserved")
print("PASS: final content type and bytes are preserved")
print("PASS: every download hop uses its independently validated destination")

print("\n[48] terminal HTTP status determines download success")

def status_resolver(hostname):
    assert hostname == "journal.example"
    return ["8.8.8.8"]

def make_status_requester(status_code, content=b"response-body"):
    def requester(url, destination):
        return academic_claims.HTTPHopResponse(
            status_code=status_code,
            location=None,
            content_type="application/pdf",
            content=content,
        )
    return requester

for error_status in (404, 500):
    try:
        academic_claims.download_validated_http_source(
            "https://journal.example/article.pdf",
            requester=make_status_requester(error_status),
            resolver=status_resolver,
        )
    except academic_claims.SourceRetrievalError:
        pass
    else:
        raise AssertionError(
            f"HTTP {error_status} must not become a successful download."
        )

partial_download = academic_claims.download_validated_http_source(
    "https://journal.example/article.pdf",
    requester=make_status_requester(206, b"partial-pdf"),
    resolver=status_resolver,
)

assert partial_download.status == "downloaded"
assert partial_download.content == b"partial-pdf"
assert partial_download.content_type == "application/pdf"

print("PASS: terminal HTTP 404 is rejected")
print("PASS: terminal HTTP 500 is rejected")
print("PASS: successful 2xx response remains downloadable")
print("PASS: download layer accepts 2xx rather than requiring exactly 200")

print("\n[49] downloaded source becomes retrieved only after substantive extraction")

downloaded_pdf = academic_claims.DownloadedSource(
    status="downloaded",
    requested_url="https://journal.example/article",
    final_url="https://cdn.example/article.pdf",
    content_type="application/pdf",
    content=b"%PDF-test-content",
    reasons=["Test download."],
)

extractor_inputs = []

def substantive_pdf_extractor(content):
    extractor_inputs.append(content)
    return "Methods\nParticipants were randomly allocated to two groups."

retrieved_pdf = academic_claims.extract_downloaded_source(
    downloaded_pdf,
    doi="10.1234/example",
    source="openalex",
    extractor=substantive_pdf_extractor,
)

assert retrieved_pdf.status == "retrieved"
assert retrieved_pdf.doi == "10.1234/example"
assert retrieved_pdf.source == "openalex"
assert retrieved_pdf.text == (
    "Methods\nParticipants were randomly allocated to two groups."
)
assert retrieved_pdf.locator == "https://cdn.example/article.pdf"
assert extractor_inputs == [b"%PDF-test-content"]

empty_pdf = academic_claims.DownloadedSource(
    status="downloaded",
    requested_url="https://journal.example/empty",
    final_url="https://cdn.example/empty.pdf",
    content_type="application/pdf",
    content=b"%PDF-empty",
    reasons=["Test download."],
)

empty_result = academic_claims.extract_downloaded_source(
    empty_pdf,
    doi="10.1234/empty",
    source="openalex",
    extractor=lambda content: "   ",
)

assert empty_result.status == "not_retrieved"
assert empty_result.text is None
assert empty_result.locator is None

print("PASS: downloaded bytes are passed to extraction")
print("PASS: substantive extracted text becomes RetrievedSource")
print("PASS: final source URL is retained as retrieval locator")
print("PASS: empty extraction remains not_retrieved")
print("PASS: successful download alone does not imply successful retrieval")

print("\n[50] PDF extractor preserves page order and translates parsing failure")

class FakePDFPage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class FakePDFReader:
    def __init__(self, stream):
        assert stream.read() == b"%PDF-test"
        self.pages = [
            FakePDFPage("First page text."),
            FakePDFPage(None),
            FakePDFPage("Third page text."),
        ]


pdf_text = academic_claims.extract_pdf_text(
    b"%PDF-test",
    reader_factory=FakePDFReader,
)

assert pdf_text == "First page text.\n\nThird page text."

print("PASS: PDF bytes are supplied through an in-memory stream")
print("PASS: extractable pages remain in document order")
print("PASS: empty PDF pages do not create false textual content")
print("PASS: extracted pages use deterministic paragraph separation")


class FailingPDFReader:
    def __init__(self, stream):
        from pypdf.errors import PdfReadError
        raise PdfReadError("malformed PDF")


try:
    academic_claims.extract_pdf_text(
        b"not-a-pdf",
        reader_factory=FailingPDFReader,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Expected PDF parsing failure to become SourceRetrievalError."
    )

print("PASS: expected PDF parsing failure becomes SourceRetrievalError")

print("\n[51] PDF extractor does not hide unexpected programming failures")

class UnexpectedlyFailingPDFReader:
    def __init__(self, stream):
        raise ValueError("unexpected programming failure")


try:
    academic_claims.extract_pdf_text(
        b"%PDF-test",
        reader_factory=UnexpectedlyFailingPDFReader,
    )
except ValueError as exc:
    assert str(exc) == "unexpected programming failure"
else:
    raise AssertionError(
        "Unexpected non-pypdf exception should propagate unchanged."
    )

print("PASS: unexpected non-pypdf exception propagates unchanged")
print("PASS: PDF adapter does not convert arbitrary failures into retrieval failures")

print("\n[52] discovered PDF source composes download and extraction")

location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/composed",
    source="openalex",
    landing_page_url=None,
    pdf_url="https://cdn.example/article.pdf",
    is_oa=True,
    reasons=["Test source location."],
)

download_calls = []

def fake_pdf_downloader(url):
    download_calls.append(url)
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url="https://cdn.example/final-article.pdf",
        content_type="application/pdf",
        content=b"%PDF-composed",
        reasons=["Test download."],
    )


extractor_calls = []

def fake_pdf_extractor(content):
    extractor_calls.append(content)
    return "Results\nThe intervention group improved by 2.4 cm."


retrieved = academic_claims.retrieve_pdf_source_from_location(
    location,
    downloader=fake_pdf_downloader,
    extractor=fake_pdf_extractor,
)

assert download_calls == ["https://cdn.example/article.pdf"]
assert extractor_calls == [b"%PDF-composed"]
assert retrieved.status == "retrieved"
assert retrieved.doi == "10.1234/composed"
assert retrieved.source == "openalex"
assert retrieved.text == (
    "Results\nThe intervention group improved by 2.4 cm."
)
assert retrieved.locator == "https://cdn.example/final-article.pdf"

print("PASS: discovered PDF URL is passed to downloader only")
print("PASS: downloaded bytes are passed to extractor")
print("PASS: bibliographic DOI and source survive composition")
print("PASS: extracted text becomes RetrievedSource")
print("PASS: final redirected source URL survives as locator")

print("\n[53] composed PDF retrieval preserves controlled failure states")

no_pdf_location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/no-pdf",
    source="openalex",
    landing_page_url="https://journal.example/article",
    pdf_url=None,
    is_oa=True,
    reasons=["Test source location without PDF."],
)

downloader_called = []

def downloader_must_not_run(url):
    downloader_called.append(url)
    raise AssertionError("Downloader should not run without a PDF URL.")


no_pdf_result = academic_claims.retrieve_pdf_source_from_location(
    no_pdf_location,
    downloader=downloader_must_not_run,
)

assert no_pdf_result.status == "not_retrieved"
assert no_pdf_result.doi == "10.1234/no-pdf"
assert no_pdf_result.source == "openalex"
assert no_pdf_result.text is None
assert no_pdf_result.locator is None
assert downloader_called == []

print("PASS: missing PDF URL remains not_retrieved")
print("PASS: missing PDF URL does not invoke downloader")


failed_download_location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/download-failure",
    source="openalex",
    landing_page_url=None,
    pdf_url="https://cdn.example/failure.pdf",
    is_oa=True,
    reasons=["Test source location with failed download."],
)

extractor_called = []

def failing_downloader(url):
    assert url == "https://cdn.example/failure.pdf"
    raise academic_claims.SourceRetrievalError("controlled download failure")


def extractor_must_not_run(content):
    extractor_called.append(content)
    raise AssertionError("Extractor should not run after failed download.")


failed_download_result = academic_claims.retrieve_pdf_source_from_location(
    failed_download_location,
    downloader=failing_downloader,
    extractor=extractor_must_not_run,
)

assert failed_download_result.status == "not_retrieved"
assert failed_download_result.doi == "10.1234/download-failure"
assert failed_download_result.source == "openalex"
assert failed_download_result.text is None
assert failed_download_result.locator is None
assert extractor_called == []

print("PASS: controlled download failure remains not_retrieved")
print("PASS: failed download does not invoke extractor")
print("PASS: bibliographic provenance survives controlled retrieval failure")

print("\n[54] claim passage locator identifies candidate evidence without judging support")

retrieved_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/passage",
    source="openalex",
    text=(
        "Introduction\n"
        "Jump performance is commonly assessed in basketball players.\n\n"
        "Methods\n"
        "Eighteen athletes completed the intervention over six weeks.\n\n"
        "Results\n"
        "Mean jump height increased by 2.4 cm after the intervention.\n\n"
        "Discussion\n"
        "The findings should be interpreted in light of the small sample."
    ),
    locator="https://cdn.example/article.pdf",
    reasons=["Test retrieved source."],
)

claim = "The intervention increased mean jump height by 2.4 cm."

evidence = academic_claims.locate_claim_passages(
    retrieved_source,
    claim,
    max_passages=2,
)

assert evidence
assert isinstance(evidence[0], academic_claims.ClaimEvidence)
assert "2.4 cm" in evidence[0].text
assert "jump height" in evidence[0].text.lower()
assert evidence[0].locator == "https://cdn.example/article.pdf"
assert evidence[0].source == "openalex"

print("PASS: lexical locator returns candidate ClaimEvidence")
print("PASS: most relevant passage contains the distinctive claim details")
print("PASS: source locator survives passage location")
print("PASS: source provenance survives passage location")
print("PASS: passage location makes no support-status judgement")

print("\n[55] passage location remains lexical and conservative")

contradictory_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/contradiction",
    source="openalex",
    text=(
        "Results\n"
        "Mean jump height did not increase by 2.4 cm after the intervention.\n\n"
        "Discussion\n"
        "Further research is required."
    ),
    locator="https://cdn.example/contradiction.pdf",
    reasons=["Test retrieved source."],
)

contradictory_evidence = academic_claims.locate_claim_passages(
    contradictory_source,
    "The intervention increased mean jump height by 2.4 cm.",
)

assert contradictory_evidence
assert "did not increase" in contradictory_evidence[0].text.lower()

print("PASS: contradictory passage can still be located as candidate evidence")
print("PASS: lexical location does not silently become support assessment")


unretrieved_source = academic_claims.RetrievedSource(
    status="not_retrieved",
    doi="10.1234/unretrieved",
    source="openalex",
    text=None,
    locator=None,
    reasons=["Test source was not retrieved."],
)

assert academic_claims.locate_claim_passages(
    unretrieved_source,
    "The intervention increased mean jump height by 2.4 cm.",
) == []

assert academic_claims.locate_claim_passages(
    retrieved_source,
    "",
) == []

assert academic_claims.locate_claim_passages(
    retrieved_source,
    "the and of to",
) == []

assert academic_claims.locate_claim_passages(
    retrieved_source,
    claim,
    max_passages=0,
) == []

print("PASS: unretrieved source cannot produce candidate evidence")
print("PASS: empty claim cannot produce candidate evidence")
print("PASS: stop-word-only claim cannot produce candidate evidence")
print("PASS: non-positive passage limit returns no evidence")

print("\n[56] passage locator recognises decimals and paragraph boundaries")

decimal_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/decimal",
    source="openalex",
    text=(
        "Background\n"
        "Jump height was measured before and after training.\n\n"
        "Results\n"
        "The observed change was 2.4 cm.\n\n"
        "Discussion\n"
        "Jump height findings require cautious interpretation."
    ),
    locator="https://cdn.example/decimal.pdf",
    reasons=["Test retrieved source."],
)

decimal_evidence = academic_claims.locate_claim_passages(
    decimal_source,
    "The observed change was 2.4 cm.",
    max_passages=1,
)

assert len(decimal_evidence) == 1
assert decimal_evidence[0].text == (
    "Results\n"
    "The observed change was 2.4 cm."
)

print("PASS: paragraph boundaries restrict candidate evidence")
print("PASS: decimal-bearing result paragraph ranks independently")


decimal_discriminator_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/decimal-discriminator",
    source="openalex",
    text=(
        "Results A\n"
        "The observed change was 3.7 cm.\n\n"
        "Results B\n"
        "The observed change was 2.4 cm."
    ),
    locator="https://cdn.example/decimal-discriminator.pdf",
    reasons=["Test retrieved source."],
)

decimal_discriminator_evidence = academic_claims.locate_claim_passages(
    decimal_discriminator_source,
    "The observed change was 2.4 cm.",
    max_passages=1,
)

assert decimal_discriminator_evidence[0].text == (
    "Results B\n"
    "The observed change was 2.4 cm."
)

print("PASS: decimal value itself discriminates otherwise similar passages")

print("\n[57] claim support preparation stops at evidence location")

not_retrieved_for_claim = academic_claims.RetrievedSource(
    status="not_retrieved",
    doi="10.1234/state-unretrieved",
    source="openalex",
    text=None,
    locator=None,
    reasons=["Source could not be retrieved."],
)

unretrieved_result = academic_claims.prepare_claim_support(
    not_retrieved_for_claim,
    "The intervention increased jump height.",
)

assert isinstance(unretrieved_result, academic_claims.ClaimSupportResult)
assert unretrieved_result.status == "source_not_retrieved"
assert unretrieved_result.source_status == "not_retrieved"
assert unretrieved_result.claim_status == "not_assessed"
assert unretrieved_result.evidence == []
assert unretrieved_result.doi == "10.1234/state-unretrieved"

print("PASS: unavailable source remains source_not_retrieved")
print("PASS: unavailable source does not become a claim judgement")


retrieved_without_match = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/state-not-located",
    source="openalex",
    text=(
        "Methods\n"
        "Participants completed questionnaires at baseline.\n\n"
        "Discussion\n"
        "Future research should use larger samples."
    ),
    locator="https://cdn.example/not-located.pdf",
    reasons=["Test retrieved source."],
)

not_located_result = academic_claims.prepare_claim_support(
    retrieved_without_match,
    "Mean sprint velocity increased by 1.8 metres per second.",
)

assert not_located_result.status == "claim_not_located"
assert not_located_result.source_status == "retrieved"
assert not_located_result.claim_status == "not_located"
assert not_located_result.evidence == []
assert not_located_result.doi == "10.1234/state-not-located"

print("PASS: retrieved source without candidate evidence becomes claim_not_located")


retrieved_with_match = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/state-located",
    source="openalex",
    text=(
        "Methods\n"
        "Eighteen athletes completed six weeks of training.\n\n"
        "Results\n"
        "Mean jump height increased by 2.4 cm after the intervention."
    ),
    locator="https://cdn.example/located.pdf",
    reasons=["Test retrieved source."],
)

located_result = academic_claims.prepare_claim_support(
    retrieved_with_match,
    "Mean jump height increased by 2.4 cm after the intervention.",
)

assert located_result.status == "claim_located"
assert located_result.source_status == "retrieved"
assert located_result.claim_status == "located"
assert located_result.evidence
assert "2.4 cm" in located_result.evidence[0].text
assert located_result.doi == "10.1234/state-located"

assert located_result.status not in {
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
}
assert located_result.claim_status not in {
    "supported",
    "partially_supported",
    "not_supported",
}

print("PASS: located evidence becomes claim_located")
print("PASS: candidate evidence is preserved for later assessment")
print("PASS: passage location cannot itself produce a support judgement")

print("\n[58] unusable claim input does not become claim_not_located")

retrieved_for_input_checks = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/input-checks",
    source="openalex",
    text=(
        "Results\n"
        "Mean jump height increased by 2.4 cm after the intervention."
    ),
    locator="https://cdn.example/input-checks.pdf",
    reasons=["Test retrieved source."],
)

empty_claim_result = academic_claims.prepare_claim_support(
    retrieved_for_input_checks,
    "",
)

assert empty_claim_result.status == "claim_not_assessed"
assert empty_claim_result.source_status == "retrieved"
assert empty_claim_result.claim_status == "not_assessed"
assert empty_claim_result.evidence == []

print("PASS: empty claim remains not_assessed")


stopword_claim_result = academic_claims.prepare_claim_support(
    retrieved_for_input_checks,
    "the and of to",
)

assert stopword_claim_result.status == "claim_not_assessed"
assert stopword_claim_result.source_status == "retrieved"
assert stopword_claim_result.claim_status == "not_assessed"
assert stopword_claim_result.evidence == []

print("PASS: claim without searchable content remains not_assessed")


missing_locator_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/missing-locator",
    source="openalex",
    text="Mean jump height increased by 2.4 cm.",
    locator=None,
    reasons=["Synthetic retrieved source without locator."],
)

missing_locator_result = academic_claims.prepare_claim_support(
    missing_locator_source,
    "Mean jump height increased by 2.4 cm.",
)

assert missing_locator_result.status == "claim_not_assessed"
assert missing_locator_result.source_status == "retrieved"
assert missing_locator_result.claim_status == "not_assessed"
assert missing_locator_result.evidence == []

print("PASS: missing evidence locator remains not_assessed")


zero_limit_result = academic_claims.prepare_claim_support(
    retrieved_for_input_checks,
    "Mean jump height increased by 2.4 cm.",
    max_passages=0,
)

assert zero_limit_result.status == "claim_not_assessed"
assert zero_limit_result.source_status == "retrieved"
assert zero_limit_result.claim_status == "not_assessed"
assert zero_limit_result.evidence == []

print("PASS: disabled passage search remains not_assessed")
print("PASS: claim_not_located is reserved for an attempted meaningful search")

print("\n[59] PDF page extraction preserves page identity")

class PageAwareFakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class PageAwareFakeReader:
    def __init__(self, stream):
        assert stream.read() == b"%PDF-page-aware"
        self.pages = [
            PageAwareFakePage("First page text."),
            PageAwareFakePage(None),
            PageAwareFakePage("Third page text."),
        ]


pages = academic_claims.extract_pdf_pages(
    b"%PDF-page-aware",
    reader_factory=PageAwareFakeReader,
)

assert len(pages) == 3
assert isinstance(pages[0], academic_claims.ExtractedPage)

assert pages[0].page_number == 1
assert pages[0].text == "First page text."

assert pages[1].page_number == 2
assert pages[1].text == ""

assert pages[2].page_number == 3
assert pages[2].text == "Third page text."

print("PASS: PDF extraction preserves physical page count")
print("PASS: page numbering is one-based")
print("PASS: empty page remains represented")
print("PASS: later page identity does not shift when an earlier page has no text")


class FailingPageAwareReader:
    def __init__(self, stream):
        raise academic_claims.PyPdfError("Synthetic PDF failure")


try:
    academic_claims.extract_pdf_pages(
        b"%PDF-broken",
        reader_factory=FailingPageAwareReader,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Expected PDF processing failure to become SourceRetrievalError"
    )

print("PASS: expected PDF processing failure remains controlled")

print("\n[60] page-aware PDF extraction does not hide unexpected failures")

class UnexpectedPageAwareReader:
    def __init__(self, stream):
        raise ValueError("Synthetic unexpected failure")


try:
    academic_claims.extract_pdf_pages(
        b"%PDF-unexpected",
        reader_factory=UnexpectedPageAwareReader,
    )
except ValueError as exc:
    assert str(exc) == "Synthetic unexpected failure"
else:
    raise AssertionError(
        "Unexpected extraction failure should propagate unchanged"
    )

print("PASS: unexpected page-aware extraction failure propagates")
print("PASS: page-aware extraction catches only expected PDF processing errors")

print("\n[61] claim evidence carries optional page provenance")

paged_evidence = academic_claims.ClaimEvidence(
    text="Mean jump height increased by 2.4 cm.",
    locator="https://cdn.example/article.pdf",
    source="openalex",
    page_number=7,
)

assert paged_evidence.page_number == 7

paged_payload = paged_evidence.to_dict()
assert paged_payload["page_number"] == 7
assert paged_payload["locator"] == "https://cdn.example/article.pdf"
assert paged_payload["source"] == "openalex"

print("PASS: ClaimEvidence can preserve physical page number")
print("PASS: page provenance survives serialisation")


unpaged_evidence = academic_claims.ClaimEvidence(
    text="Relevant HTML passage.",
    locator="https://example.org/article",
    source="publisher",
)

assert unpaged_evidence.page_number is None
assert unpaged_evidence.to_dict()["page_number"] is None

print("PASS: non-paginated evidence remains valid")
print("PASS: page provenance is optional rather than fabricated")

print("\n[62] page-aware claim location preserves physical page provenance")

page_source = [
    academic_claims.ExtractedPage(
        page_number=1,
        text="Background\nJump performance is commonly assessed in basketball.",
    ),
    academic_claims.ExtractedPage(
        page_number=2,
        text="",
    ),
    academic_claims.ExtractedPage(
        page_number=3,
        text=(
            "Results\n"
            "Mean jump height increased by 2.4 cm after the intervention."
        ),
    ),
]

page_evidence = academic_claims.locate_claim_passages_in_pages(
    page_source,
    "Mean jump height increased by 2.4 cm after the intervention.",
    locator="https://cdn.example/page-aware.pdf",
    source="openalex",
    max_passages=2,
)

assert page_evidence
assert isinstance(page_evidence[0], academic_claims.ClaimEvidence)
assert page_evidence[0].page_number == 3
assert "2.4 cm" in page_evidence[0].text
assert page_evidence[0].locator == "https://cdn.example/page-aware.pdf"
assert page_evidence[0].source == "openalex"

print("PASS: relevant passage retains physical page number")
print("PASS: empty preceding page does not shift evidence provenance")
print("PASS: PDF locator survives page-aware claim location")
print("PASS: scholarly source provenance survives page-aware claim location")


no_match_page_evidence = academic_claims.locate_claim_passages_in_pages(
    page_source,
    "Sprint velocity increased by 1.8 metres per second.",
    locator="https://cdn.example/page-aware.pdf",
    source="openalex",
)

assert no_match_page_evidence == []

print("PASS: page-aware location returns no evidence when no candidate is located")

print("\n[63] claim location rejects incidental lexical overlap")

incidental_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/incidental",
    source="openalex",
    text=(
        "Results\n"
        "Mean jump height increased by 2.4 cm after the intervention."
    ),
    locator="https://cdn.example/incidental.pdf",
    reasons=["Test retrieved source."],
)

incidental_claim = "Sprint velocity increased by 1.8 metres per second."

assert academic_claims.locate_claim_passages(
    incidental_source,
    incidental_claim,
) == []

print("PASS: flattened locator rejects one-word incidental overlap")


incidental_pages = [
    academic_claims.ExtractedPage(
        page_number=3,
        text=(
            "Results\n"
            "Mean jump height increased by 2.4 cm after the intervention."
        ),
    ),
]

assert academic_claims.locate_claim_passages_in_pages(
    incidental_pages,
    incidental_claim,
    locator="https://cdn.example/incidental.pdf",
    source="openalex",
) == []

print("PASS: page-aware locator rejects one-word incidental overlap")


meaningful_source = academic_claims.RetrievedSource(
    status="retrieved",
    doi="10.1234/meaningful",
    source="openalex",
    text=(
        "Results\n"
        "Sprint velocity increased following the intervention."
    ),
    locator="https://cdn.example/meaningful.pdf",
    reasons=["Test retrieved source."],
)

meaningful_claim = "Sprint velocity increased after training."

meaningful_evidence = academic_claims.locate_claim_passages(
    meaningful_source,
    meaningful_claim,
)

assert meaningful_evidence
assert "Sprint velocity increased" in meaningful_evidence[0].text

print("PASS: multiple substantive overlapping terms remain candidate evidence")
print("PASS: lexical threshold remains a location heuristic, not support assessment")

print("\n[64] page-aware PDF extraction composes with claim location")

class ComposedFakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class ComposedFakeReader:
    def __init__(self, stream):
        self.pages = [
            ComposedFakePage(
                "Background\n"
                "Jump performance is commonly assessed in basketball."
            ),
            ComposedFakePage(None),
            ComposedFakePage(
                "Results\n"
                "Mean jump height increased by 2.4 cm after the intervention."
            ),
        ]


composed_evidence = academic_claims.locate_pdf_claim_passages(
    b"%PDF-synthetic",
    "Mean jump height increased by 2.4 cm after the intervention.",
    locator="https://cdn.example/composed.pdf",
    source="openalex",
    max_passages=2,
    reader_factory=ComposedFakeReader,
)

assert composed_evidence
assert len(composed_evidence) == 1
assert isinstance(composed_evidence[0], academic_claims.ClaimEvidence)
assert composed_evidence[0].page_number == 3
assert "2.4 cm" in composed_evidence[0].text
assert composed_evidence[0].locator == "https://cdn.example/composed.pdf"
assert composed_evidence[0].source == "openalex"

print("PASS: PDF bytes compose directly with page-aware claim location")
print("PASS: composed evidence preserves physical page number")
print("PASS: composed evidence preserves source locator")
print("PASS: composed evidence preserves scholarly source provenance")

print("\n[65] composed PDF claim location preserves extraction failure")

class FailingComposedReader:
    def __init__(self, stream):
        raise academic_claims.PyPdfError("synthetic PDF failure")


try:
    academic_claims.locate_pdf_claim_passages(
        b"%PDF-broken",
        "Mean jump height increased by 2.4 cm.",
        locator="https://cdn.example/broken.pdf",
        source="openalex",
        reader_factory=FailingComposedReader,
    )
except academic_claims.SourceRetrievalError as exc:
    assert "PDF page text extraction failed" in str(exc)
else:
    raise AssertionError(
        "Expected SourceRetrievalError from failed PDF extraction"
    )

print("PASS: expected PDF processing failure propagates through composition")
print("PASS: extraction failure does not become empty candidate evidence")


class UnexpectedFailingComposedReader:
    def __init__(self, stream):
        raise ValueError("unexpected parser failure")


try:
    academic_claims.locate_pdf_claim_passages(
        b"%PDF-unexpected",
        "Mean jump height increased by 2.4 cm.",
        locator="https://cdn.example/unexpected.pdf",
        source="openalex",
        reader_factory=UnexpectedFailingComposedReader,
    )
except ValueError as exc:
    assert str(exc) == "unexpected parser failure"
else:
    raise AssertionError(
        "Expected unexpected extraction failure to propagate unchanged"
    )

print("PASS: unexpected extraction failure is not hidden by composition")

print("\n[66] downloaded PDF composes with page-aware claim evidence")

download_location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/page-aware-download",
    source="openalex",
    landing_page_url="https://example.org/article",
    pdf_url="https://example.org/original.pdf",
    is_oa=True,
    reasons=["Synthetic source location."],
)

download_calls = []


def fake_page_aware_downloader(url):
    download_calls.append(url)
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url="https://cdn.example/final.pdf",
        content_type="application/pdf",
        content=b"%PDF-synthetic",
        reasons=["Synthetic validated download."],
    )


class DownloadedFakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class DownloadedFakeReader:
    def __init__(self, stream):
        self.pages = [
            DownloadedFakePage(
                "Background\n"
                "Jump performance was assessed before the intervention."
            ),
            DownloadedFakePage(""),
            DownloadedFakePage(
                "Results\n"
                "Mean jump height increased by 2.4 cm after the intervention."
            ),
        ]


downloaded_evidence = academic_claims.locate_pdf_claim_from_location(
    download_location,
    "Mean jump height increased by 2.4 cm after the intervention.",
    downloader=fake_page_aware_downloader,
    reader_factory=DownloadedFakeReader,
)

assert download_calls == ["https://example.org/original.pdf"]
assert downloaded_evidence
assert len(downloaded_evidence) <= 2
assert downloaded_evidence[0].page_number == 3
assert "2.4 cm" in downloaded_evidence[0].text
assert downloaded_evidence[0].locator == "https://cdn.example/final.pdf"
assert downloaded_evidence[0].source == "openalex"

print("PASS: discovered PDF URL is passed to downloader")
print("PASS: downloaded PDF composes with page-aware claim location")
print("PASS: physical page provenance survives downloaded-source composition")
print("PASS: final validated download URL becomes evidence locator")
print("PASS: scholarly discovery source remains explicit")

print("\n[67] unavailable PDF source is distinct from no located claim")

no_pdf_location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/no-pdf",
    source="openalex",
    landing_page_url="https://example.org/article",
    pdf_url=None,
    is_oa=True,
    reasons=["No PDF URL available."],
)

unexpected_download_calls = []


def should_not_download(url):
    unexpected_download_calls.append(url)
    raise AssertionError("Downloader should not be called without a PDF URL")


try:
    academic_claims.locate_pdf_claim_from_location(
        no_pdf_location,
        "Mean jump height increased by 2.4 cm.",
        downloader=should_not_download,
    )
except academic_claims.SourceRetrievalError as exc:
    assert "No PDF URL" in str(exc)
else:
    raise AssertionError(
        "Missing PDF URL should raise SourceRetrievalError"
    )

assert unexpected_download_calls == []

print("PASS: missing PDF URL is a retrieval failure")
print("PASS: downloader is not called when no PDF URL exists")


failed_download_location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/download-failure",
    source="openalex",
    landing_page_url="https://example.org/article",
    pdf_url="https://example.org/article.pdf",
    is_oa=True,
    reasons=["Synthetic source location."],
)


def failed_downloader(url):
    return academic_claims.DownloadedSource(
        status="not_retrieved",
        requested_url=url,
        final_url=url,
        content_type=None,
        content=b"",
        reasons=["Synthetic download failure."],
    )


try:
    academic_claims.locate_pdf_claim_from_location(
        failed_download_location,
        "Mean jump height increased by 2.4 cm.",
        downloader=failed_downloader,
    )
except academic_claims.SourceRetrievalError as exc:
    assert "not successfully downloaded" in str(exc)
else:
    raise AssertionError(
        "Failed PDF download should raise SourceRetrievalError"
    )

print("PASS: failed PDF download remains a retrieval failure")


class NoMatchDownloadedReader:
    def __init__(self, stream):
        self.pages = [
            DownloadedFakePage(
                "Participants completed questionnaires at baseline."
            ),
            DownloadedFakePage(
                "Demographic characteristics are presented descriptively."
            ),
        ]


def successful_no_match_downloader(url):
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url="https://cdn.example/no-match.pdf",
        content_type="application/pdf",
        content=b"%PDF-synthetic",
        reasons=["Synthetic successful download."],
    )


no_match_evidence = academic_claims.locate_pdf_claim_from_location(
    failed_download_location,
    "Mean jump height increased by 2.4 cm.",
    downloader=successful_no_match_downloader,
    reader_factory=NoMatchDownloadedReader,
)

assert no_match_evidence == []

print("PASS: successfully searched PDF may legitimately return no candidate")
print("PASS: retrieval failure remains distinct from claim not located")

print("\n[68] page-aware evidence maps to claim-support location states")

located_page_evidence = [
    academic_claims.ClaimEvidence(
        text="Mean jump height increased by 2.4 cm after the intervention.",
        locator="https://cdn.example/article.pdf",
        source="openalex",
        page_number=7,
    )
]

located_support = academic_claims.prepare_page_aware_claim_support(
    doi="10.1234/page-aware-support",
    evidence=located_page_evidence,
    search_attempted=True,
)

assert located_support.status == "claim_located"
assert located_support.source_status == "retrieved"
assert located_support.claim_status == "located"
assert located_support.doi == "10.1234/page-aware-support"
assert located_support.evidence == located_page_evidence
assert located_support.evidence[0].page_number == 7

located_payload = located_support.to_dict()
assert located_payload["evidence"][0]["page_number"] == 7

print("PASS: located page-aware evidence becomes claim_located")
print("PASS: physical page provenance survives ClaimSupportResult")
print("PASS: page provenance survives ClaimSupportResult serialisation")


not_located_support = academic_claims.prepare_page_aware_claim_support(
    doi="10.1234/page-aware-support",
    evidence=[],
    search_attempted=True,
)

assert not_located_support.status == "claim_not_located"
assert not_located_support.source_status == "retrieved"
assert not_located_support.claim_status == "not_located"
assert not_located_support.evidence == []

print("PASS: meaningful page-aware search with no candidate becomes claim_not_located")


not_assessed_support = academic_claims.prepare_page_aware_claim_support(
    doi="10.1234/page-aware-support",
    evidence=[],
    search_attempted=False,
)

assert not_assessed_support.status == "claim_not_assessed"
assert not_assessed_support.source_status == "retrieved"
assert not_assessed_support.claim_status == "not_assessed"
assert not_assessed_support.evidence == []

print("PASS: page-aware source without meaningful search remains claim_not_assessed")
print("PASS: absence of evidence is interpreted using whether search was attempted")

print("\n[69] PDF claim pipeline maps retrieval and location outcomes")

pipeline_location = academic_claims.SourceLocation(
    status="located",
    doi="10.1234/pipeline",
    source="openalex",
    landing_page_url="https://example.org/article",
    pdf_url="https://example.org/article.pdf",
    is_oa=True,
    reasons=["Synthetic source location."],
)


def pipeline_failed_downloader(url):
    raise academic_claims.SourceRetrievalError(
        "Synthetic controlled download failure."
    )


failed_pipeline = academic_claims.prepare_pdf_claim_support(
    pipeline_location,
    "Mean jump height increased by 2.4 cm.",
    downloader=pipeline_failed_downloader,
)

assert failed_pipeline.status == "source_not_retrieved"
assert failed_pipeline.source_status == "not_retrieved"
assert failed_pipeline.claim_status == "not_assessed"
assert failed_pipeline.doi == "10.1234/pipeline"
assert failed_pipeline.evidence == []

print("PASS: controlled PDF retrieval failure becomes source_not_retrieved")
print("PASS: retrieval failure does not become claim_not_located")


class PipelineMatchReader:
    def __init__(self, stream):
        self.pages = [
            DownloadedFakePage("Background information."),
            DownloadedFakePage(
                "Mean jump height increased by 2.4 cm after the intervention."
            ),
        ]


def pipeline_success_downloader(url):
    return academic_claims.DownloadedSource(
        status="downloaded",
        requested_url=url,
        final_url="https://cdn.example/pipeline.pdf",
        content_type="application/pdf",
        content=b"%PDF-synthetic",
        reasons=["Synthetic successful download."],
    )


located_pipeline = academic_claims.prepare_pdf_claim_support(
    pipeline_location,
    "Mean jump height increased by 2.4 cm after the intervention.",
    downloader=pipeline_success_downloader,
    reader_factory=PipelineMatchReader,
)

assert located_pipeline.status == "claim_located"
assert located_pipeline.source_status == "retrieved"
assert located_pipeline.claim_status == "located"
assert located_pipeline.evidence
assert located_pipeline.evidence[0].page_number == 2
assert located_pipeline.evidence[0].locator == "https://cdn.example/pipeline.pdf"
assert located_pipeline.evidence[0].source == "openalex"

print("PASS: successful PDF pipeline becomes claim_located")
print("PASS: page and final-URL provenance survive full composition")


class PipelineNoMatchReader:
    def __init__(self, stream):
        self.pages = [
            DownloadedFakePage(
                "Participants completed demographic questionnaires."
            ),
        ]


not_located_pipeline = academic_claims.prepare_pdf_claim_support(
    pipeline_location,
    "Mean jump height increased by 2.4 cm.",
    downloader=pipeline_success_downloader,
    reader_factory=PipelineNoMatchReader,
)

assert not_located_pipeline.status == "claim_not_located"
assert not_located_pipeline.source_status == "retrieved"
assert not_located_pipeline.claim_status == "not_located"
assert not_located_pipeline.evidence == []

print("PASS: successful meaningful search with no candidate becomes claim_not_located")

print("\n[70] PDF claim pipeline distinguishes unsearchable claims")

unsearchable_pipeline = academic_claims.prepare_pdf_claim_support(
    pipeline_location,
    "the and of",
    downloader=pipeline_success_downloader,
    reader_factory=PipelineMatchReader,
)

assert unsearchable_pipeline.status == "claim_not_assessed"
assert unsearchable_pipeline.source_status == "retrieved"
assert unsearchable_pipeline.claim_status == "not_assessed"
assert unsearchable_pipeline.evidence == []

print("PASS: retrieved PDF with no searchable claim terms becomes claim_not_assessed")
print("PASS: unsearchable claim is not misreported as claim_not_located")

print("\n[71] claim evidence assessment has an auditable data contract")

assessment_evidence = [
    academic_claims.ClaimEvidence(
        text="Mean jump height increased by 2.4 cm after the intervention.",
        locator="https://cdn.example/article.pdf",
        source="openalex",
        page_number=7,
    )
]

supported_assessment = academic_claims.ClaimAssessmentResult(
    status="claim_supported",
    claim="The intervention increased mean jump height by 2.4 cm.",
    evidence=assessment_evidence,
    reasons=[
        "Located evidence agrees with the claimed outcome, direction, and value."
    ],
)

assert supported_assessment.status == "claim_supported"
assert (
    supported_assessment.claim
    == "The intervention increased mean jump height by 2.4 cm."
)
assert supported_assessment.evidence == assessment_evidence
assert supported_assessment.evidence[0].page_number == 7
assert supported_assessment.reasons == [
    "Located evidence agrees with the claimed outcome, direction, and value."
]

supported_payload = supported_assessment.to_dict()

assert supported_payload["status"] == "claim_supported"
assert (
    supported_payload["claim"]
    == "The intervention increased mean jump height by 2.4 cm."
)
assert supported_payload["evidence"][0]["text"] == assessment_evidence[0].text
assert supported_payload["evidence"][0]["page_number"] == 7
assert (
    supported_payload["evidence"][0]["locator"]
    == "https://cdn.example/article.pdf"
)
assert supported_payload["evidence"][0]["source"] == "openalex"
assert supported_payload["reasons"] == supported_assessment.reasons

print("PASS: assessment status is explicit")
print("PASS: original claim remains auditable")
print("PASS: located evidence remains attached to assessment")
print("PASS: physical page provenance survives assessment serialisation")
print("PASS: source and final locator survive assessment serialisation")
print("PASS: assessment reasons are explicit")


for assessment_status in (
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
    "claim_contradicted",
):
    result = academic_claims.ClaimAssessmentResult(
        status=assessment_status,
        claim="Synthetic claim.",
        evidence=assessment_evidence,
        reasons=["Synthetic assessment reason."],
    )

    assert result.status == assessment_status
    assert result.to_dict()["status"] == assessment_status

print("PASS: all four planned assessment outcomes fit the same contract")


contradictory_evidence = [
    academic_claims.ClaimEvidence(
        text="Mean jump height did not increase by 2.4 cm after the intervention.",
        locator="https://cdn.example/article.pdf",
        source="openalex",
        page_number=8,
    )
]

contradicted_assessment = academic_claims.ClaimAssessmentResult(
    status="claim_contradicted",
    claim="The intervention increased mean jump height by 2.4 cm.",
    evidence=contradictory_evidence,
    reasons=["Synthetic contradiction assessment."],
)

assert contradicted_assessment.evidence[0].text == contradictory_evidence[0].text
assert "did not increase" in contradicted_assessment.evidence[0].text

print("PASS: contradictory evidence remains unchanged rather than being rewritten")
print("PASS: assessment contract records judgement without performing it")

print("\n[72] assessor output is strictly validated before provenance is attached")

valid_assessor_output = {
    "status": "claim_supported",
    "reason": (
        "The located evidence agrees with the claimed outcome, "
        "direction, and value."
    ),
}

validated_assessment = academic_claims.build_claim_assessment(
    claim="The intervention increased mean jump height by 2.4 cm.",
    evidence=assessment_evidence,
    assessor_output=valid_assessor_output,
)

assert validated_assessment.status == "claim_supported"
assert (
    validated_assessment.claim
    == "The intervention increased mean jump height by 2.4 cm."
)
assert validated_assessment.evidence is assessment_evidence
assert validated_assessment.reasons == [
    "The located evidence agrees with the claimed outcome, direction, and value."
]

print("PASS: valid assessor output builds ClaimAssessmentResult")
print("PASS: original application-owned claim is retained")
print("PASS: original application-owned evidence is retained")
print("PASS: assessor reason is retained")


for allowed_status in (
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
    "claim_contradicted",
):
    result = academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=assessment_evidence,
        assessor_output={
            "status": allowed_status,
            "reason": "Synthetic grounded reason.",
        },
    )
    assert result.status == allowed_status

print("PASS: exactly the four planned assessment statuses are accepted")


invalid_statuses = (
    "supported",
    "claim_verified",
    "probably_supported",
    "claim_located",
    "",
)

for invalid_status in invalid_statuses:
    try:
        academic_claims.build_claim_assessment(
            claim="Synthetic claim.",
            evidence=assessment_evidence,
            assessor_output={
                "status": invalid_status,
                "reason": "Synthetic reason.",
            },
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            f"Invalid assessor status was accepted: {invalid_status!r}"
        )

print("PASS: invented or upstream statuses are rejected")


for bad_output in (
    {},
    {"status": "claim_supported"},
    {"reason": "Missing status."},
    {
        "status": "claim_supported",
        "reason": "",
    },
    {
        "status": "claim_supported",
        "reason": "   ",
    },
):
    try:
        academic_claims.build_claim_assessment(
            claim="Synthetic claim.",
            evidence=assessment_evidence,
            assessor_output=bad_output,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            f"Malformed assessor output was accepted: {bad_output!r}"
        )

print("PASS: missing and empty required fields are rejected")


try:
    academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=assessment_evidence,
        assessor_output={
            "status": "claim_supported",
            "reason": "Synthetic reason.",
            "claim": "Model-rewritten claim.",
        },
    )
except ValueError:
    pass
else:
    raise AssertionError("Unexpected assessor field was accepted")

print("PASS: unexpected fields are rejected")
print("PASS: assessor cannot supply or rewrite the claim")


try:
    academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=assessment_evidence,
        assessor_output={
            "status": "claim_supported",
            "reason": "Synthetic reason.",
            "evidence": [
                {
                    "text": "Model-generated evidence.",
                    "page_number": 999,
                }
            ],
        },
    )
except ValueError:
    pass
else:
    raise AssertionError("Model-supplied evidence was accepted")

print("PASS: assessor cannot supply or rewrite evidence provenance")


try:
    academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=assessment_evidence,
        assessor_output={
            "status": "claim_supported",
            "reason": 42,
        },
    )
except ValueError:
    pass
else:
    raise AssertionError("Non-string assessor reason was accepted")

print("PASS: assessor reason must be text")


try:
    academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=assessment_evidence,
        assessor_output="claim_supported",
    )
except ValueError:
    pass
else:
    raise AssertionError("Non-object assessor output was accepted")

print("PASS: assessor output must be an object")
print("PASS: assessor judgement is separated from application-owned provenance")

print("\n[73] semantic assessment requires located application-owned evidence")

for assessment_status in (
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
    "claim_contradicted",
):
    try:
        academic_claims.build_claim_assessment(
            claim="Synthetic claim.",
            evidence=[],
            assessor_output={
                "status": assessment_status,
                "reason": "Synthetic assessment reason.",
            },
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            f"Assessment without evidence was accepted: {assessment_status!r}"
        )

print("PASS: no assessment status is accepted without located evidence")


try:
    academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=None,
        assessor_output={
            "status": "claim_supported",
            "reason": "Synthetic assessment reason.",
        },
    )
except ValueError:
    pass
else:
    raise AssertionError("Assessment with evidence=None was accepted")

print("PASS: missing evidence cannot enter semantic assessment")


try:
    academic_claims.build_claim_assessment(
        claim="Synthetic claim.",
        evidence=["model-generated passage"],
        assessor_output={
            "status": "claim_supported",
            "reason": "Synthetic assessment reason.",
        },
    )
except ValueError:
    pass
else:
    raise AssertionError("Non-ClaimEvidence input was accepted")

print("PASS: semantic assessment requires ClaimEvidence objects")
print("PASS: assessment remains strictly downstream of claim location")

print("\n[74] claim assessor has a strict structured-output schema")

schema = academic_claims.claim_assessment_output_schema()

assert schema["type"] == "object"
assert schema["additionalProperties"] is False
assert set(schema["required"]) == {"status", "reason"}
assert set(schema["properties"]) == {"status", "reason"}

status_schema = schema["properties"]["status"]
reason_schema = schema["properties"]["reason"]

assert status_schema["type"] == "string"
assert status_schema["enum"] == [
    "claim_supported",
    "claim_partially_supported",
    "claim_not_supported",
    "claim_contradicted",
]

assert reason_schema["type"] == "string"
assert reason_schema["minLength"] == 1

print("PASS: assessor schema is an object with no additional properties")
print("PASS: assessor schema requires exactly status and reason")
print("PASS: schema exposes exactly the four assessment outcomes")
print("PASS: assessor reason must be non-empty text")


assert "claim" not in schema["properties"]
assert "evidence" not in schema["properties"]
assert "page_number" not in schema["properties"]
assert "locator" not in schema["properties"]
assert "source" not in schema["properties"]

print("PASS: model schema contains no application-owned claim field")
print("PASS: model schema contains no evidence or provenance fields")


schema["properties"]["status"]["enum"].append("invented_status")

fresh_schema = academic_claims.claim_assessment_output_schema()

assert "invented_status" not in fresh_schema["properties"]["status"]["enum"]

print("PASS: callers receive independent schema structures")
print("PASS: one caller cannot mutate the future assessor schema globally")


assert set(
    fresh_schema["properties"]["status"]["enum"]
) == set(academic_claims.CLAIM_ASSESSMENT_STATUSES)

print("PASS: schema statuses come from the canonical assessment vocabulary")
