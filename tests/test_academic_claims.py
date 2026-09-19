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
        return {
            "status_code": 302,
            "location": "https://cdn.example/article.pdf",
        }

    if url == "https://cdn.example/article.pdf":
        return {
            "status_code": 200,
            "location": None,
        }

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

assert aware_response["status_code"] == 200

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
