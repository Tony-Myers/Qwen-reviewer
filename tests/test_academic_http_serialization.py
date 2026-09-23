#!/usr/bin/env python3
"""Regression tests for production HTTP/1.1 request serialization."""

import sys
from pathlib import Path

import httpcore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import academic_claims


class TestStream:
    def __init__(self, writes):
        self.writes = writes
        self.response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
            b"pdf-content"
        )
        self.offset = 0

    def write(self, buffer, timeout=None):
        self.writes.append(bytes(buffer))

    def read(self, max_bytes, timeout=None):
        if self.offset >= len(self.response):
            return b""

        chunk = self.response[self.offset:self.offset + max_bytes]
        self.offset += len(chunk)
        return chunk

    def close(self):
        pass

    def start_tls(
        self,
        ssl_context,
        server_hostname=None,
        timeout=None,
    ):
        return self

    def get_extra_info(self, info):
        return None


def exercise_hop(url, hostname, address, expected_port):
    writes = []
    tcp_destinations = []
    original_connect_tcp = httpcore.SyncBackend.connect_tcp

    def test_connect_tcp(
        self,
        host,
        port,
        timeout=None,
        local_address=None,
        socket_options=None,
    ):
        tcp_destinations.append((host, port))
        return TestStream(writes)

    destination = academic_claims.ValidatedHTTPDestination(
        hostname=hostname,
        addresses=[address],
    )

    try:
        httpcore.SyncBackend.connect_tcp = test_connect_tcp

        response = academic_claims.request_validated_http_hop(
            url,
            destination=destination,
            max_bytes=1024,
        )
    finally:
        httpcore.SyncBackend.connect_tcp = original_connect_tcp

    assert tcp_destinations == [(address, expected_port)]
    assert response.status_code == 200
    assert response.content == b"pdf-content"

    return b"".join(writes)


print("\n[1] default HTTPS authority")

request_bytes = exercise_hop(
    "https://journal.example/article.pdf",
    hostname="journal.example",
    address="8.8.8.8",
    expected_port=443,
)

assert b"GET /article.pdf HTTP/1.1\r\n" in request_bytes
assert request_bytes.count(b"Host: journal.example\r\n") == 1

print("PASS: default HTTPS Host omits port")
print("PASS: validated IPv4 address remains the TCP destination")


print("\n[2] non-default HTTPS port")

request_bytes = exercise_hop(
    "https://journal.example:8443/article.pdf",
    hostname="journal.example",
    address="8.8.8.8",
    expected_port=8443,
)

assert request_bytes.count(b"Host: journal.example:8443\r\n") == 1

print("PASS: non-default HTTPS Host includes port")


print("\n[3] IPv6 authority with non-default port")

request_bytes = exercise_hop(
    "https://[2606:4700:4700::1111]:8443/article.pdf",
    hostname="2606:4700:4700::1111",
    address="2606:4700:4700::1111",
    expected_port=8443,
)

assert (
    request_bytes.count(
        b"Host: [2606:4700:4700::1111]:8443\r\n"
    )
    == 1
)

print("PASS: IPv6 Host authority is bracketed")
print("PASS: non-default IPv6 port is retained")
print("PASS: validated IPv6 address remains the TCP destination")


print("\n[4] cross-host redirect recomputes HTTP authority")

redirect_writes = []
redirect_tcp_destinations = []
original_connect_tcp = httpcore.SyncBackend.connect_tcp


class RedirectStream:
    def __init__(self, response, writes):
        self.response = response
        self.writes = writes
        self.offset = 0

    def write(self, buffer, timeout=None):
        self.writes.append(bytes(buffer))

    def read(self, max_bytes, timeout=None):
        if self.offset >= len(self.response):
            return b""

        chunk = self.response[self.offset:self.offset + max_bytes]
        self.offset += len(chunk)
        return chunk

    def close(self):
        pass

    def start_tls(
        self,
        ssl_context,
        server_hostname=None,
        timeout=None,
    ):
        return self

    def get_extra_info(self, info):
        return None


def redirect_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    redirect_tcp_destinations.append((host, port))
    hop_writes = []
    redirect_writes.append(hop_writes)

    if host == "8.8.8.8":
        response = (
            b"HTTP/1.1 302 Found\r\n"
            b"Location: https://cdn.example/article.pdf\r\n"
            b"Content-Length: 0\r\n"
            b"\r\n"
        )
    elif host == "1.1.1.1":
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Length: 11\r\n"
            b"\r\n"
            b"pdf-content"
        )
    else:
        raise AssertionError(f"Unexpected TCP destination: {host}")

    return RedirectStream(response, hop_writes)


def redirect_resolver(hostname):
    if hostname == "journal.example":
        return ["8.8.8.8"]

    if hostname == "cdn.example":
        return ["1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")


try:
    httpcore.SyncBackend.connect_tcp = redirect_connect_tcp

    redirect_response = academic_claims.fetch_with_validated_destinations(
        "https://journal.example/article",
        requester=academic_claims.request_validated_http_hop,
        resolver=redirect_resolver,
    )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp

assert redirect_response.status_code == 200
assert redirect_response.content == b"pdf-content"

assert redirect_tcp_destinations == [
    ("8.8.8.8", 443),
    ("1.1.1.1", 443),
]

assert len(redirect_writes) == 2

first_request = b"".join(redirect_writes[0])
second_request = b"".join(redirect_writes[1])

assert first_request.count(b"Host: journal.example\r\n") == 1
assert b"Host: cdn.example\r\n" not in first_request

assert second_request.count(b"Host: cdn.example\r\n") == 1
assert b"Host: journal.example\r\n" not in second_request

print("PASS: redirect first hop uses original HTTP authority")
print("PASS: redirect second hop recomputes destination HTTP authority")
print("PASS: each redirect hop retains its independently validated TCP IP")


print("\n[5] expected HTTP transport failures become retrieval failures")


class FailingHopConnection:
    failure_type = None

    def __init__(self, origin, network_backend, http1, http2):
        pass

    def handle_request(self, request):
        raise self.failure_type("synthetic HTTP transport failure")

    def close(self):
        pass


transport_failures = [
    httpcore.ConnectionNotAvailable,
    httpcore.ProxyError,
    httpcore.ConnectError,
    httpcore.ConnectTimeout,
    httpcore.ReadError,
    httpcore.ReadTimeout,
    httpcore.WriteError,
    httpcore.WriteTimeout,
    httpcore.PoolTimeout,
    httpcore.LocalProtocolError,
    httpcore.RemoteProtocolError,
    httpcore.UnsupportedProtocol,
]

transport_destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

for failure_type in transport_failures:
    FailingHopConnection.failure_type = failure_type

    try:
        academic_claims.request_validated_http_hop(
            "https://journal.example/article.pdf",
            destination=transport_destination,
            connection_factory=FailingHopConnection,
        )
    except academic_claims.SourceRetrievalError:
        pass
    except failure_type as exc:
        raise AssertionError(
            f"{failure_type.__name__} escaped the HTTP retrieval boundary"
        ) from exc
    else:
        raise AssertionError(
            f"{failure_type.__name__} should become SourceRetrievalError"
        )

print("PASS: expected httpcore transport/protocol failures become SourceRetrievalError")


print("\n[6] programming failures remain visible")


class BuggyHopConnection:
    def __init__(self, origin, network_backend, http1, http2):
        pass

    def handle_request(self, request):
        raise TypeError("synthetic programming error")

    def close(self):
        pass


try:
    academic_claims.request_validated_http_hop(
        "https://journal.example/article.pdf",
        destination=transport_destination,
        connection_factory=BuggyHopConnection,
    )
except TypeError:
    pass
except academic_claims.SourceRetrievalError as exc:
    raise AssertionError(
        "Programming error was incorrectly converted to SourceRetrievalError"
    ) from exc
else:
    raise AssertionError("Programming error should escape unchanged")

print("PASS: unrelated programming errors are not hidden")


print("\n[7] transport failure reaches retrieval layer as not_retrieved")


class IntegrationFailingConnection:
    def __init__(self, origin, network_backend, http1, http2):
        pass

    def handle_request(self, request):
        raise httpcore.ConnectError("synthetic connection failure")

    def close(self):
        pass


def integration_requester(url, destination):
    return academic_claims.request_validated_http_hop(
        url,
        destination=destination,
        connection_factory=IntegrationFailingConnection,
    )


def integration_downloader(url):
    return academic_claims.download_validated_http_source(
        url,
        requester=integration_requester,
        resolver=lambda hostname: ["8.8.8.8"],
    )


integration_location = academic_claims.SourceLocation(
    status="location_found",
    doi="10.1234/transport-failure",
    source="openalex",
    landing_page_url=None,
    pdf_url="https://journal.example/article.pdf",
    is_oa=True,
    reasons=["Synthetic transport-failure source."],
)

integration_result = academic_claims.retrieve_pdf_source_from_location(
    integration_location,
    downloader=integration_downloader,
)

assert integration_result.status == "not_retrieved"
assert integration_result.doi == "10.1234/transport-failure"
assert integration_result.source == "openalex"
assert integration_result.text is None
assert integration_result.locator is None
assert any(
    "download failed" in reason.lower()
    for reason in integration_result.reasons
)

print("PASS: real httpcore transport failure becomes not_retrieved")
print("PASS: failed transport retains bibliographic provenance")
print("PASS: failed transport does not invent source text or locator")

print("\n[8] production downloader resolves hostnames by default")

import socket


original_getaddrinfo = socket.getaddrinfo
default_dns_calls = []
default_download_requests = []


def fake_getaddrinfo(host, port, *args, **kwargs):
    default_dns_calls.append((host, port))

    if host == "journal.example":
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("8.8.8.8", port),
            ),
        ]

    raise AssertionError(f"Unexpected DNS hostname: {host}")


def default_requester(url, destination):
    default_download_requests.append(
        (url, destination.hostname, list(destination.addresses))
    )
    return academic_claims.HTTPHopResponse(
        status_code=200,
        location=None,
        content_type="application/pdf",
        content=b"default-resolver-pdf",
    )


socket.getaddrinfo = fake_getaddrinfo

try:
    default_downloaded = academic_claims.download_validated_http_source(
        "https://journal.example/article.pdf",
        requester=default_requester,
    )
finally:
    socket.getaddrinfo = original_getaddrinfo


assert default_downloaded.status == "downloaded"
assert default_downloaded.content == b"default-resolver-pdf"

assert default_dns_calls == [
    ("journal.example", 0),
]

assert default_download_requests == [
    (
        "https://journal.example/article.pdf",
        "journal.example",
        ["8.8.8.8"],
    ),
]

print("PASS: production downloader performs DNS resolution by default")
print("PASS: default DNS answer passes through destination validation")
print("PASS: requester receives only the validated numeric destination")

print("\n[9] production default resolver preserves DNS security boundary")

original_getaddrinfo = socket.getaddrinfo


def make_dns_record(address, port=0):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (
        (address, port, 0, 0)
        if family == socket.AF_INET6
        else (address, port)
    )
    return (
        family,
        socket.SOCK_STREAM,
        socket.IPPROTO_TCP,
        "",
        sockaddr,
    )


# Public answers, including a redirect, must be independently resolved.
redirect_dns_calls = []
redirect_requests = []


def redirect_getaddrinfo(host, port, *args, **kwargs):
    redirect_dns_calls.append((host, port))

    answers = {
        "journal.example": ["8.8.8.8"],
        "cdn.example": ["1.1.1.1"],
    }

    return [
        make_dns_record(address, port)
        for address in answers[host]
    ]


def redirect_requester(url, destination):
    redirect_requests.append(
        (url, destination.hostname, list(destination.addresses))
    )

    if destination.hostname == "journal.example":
        return academic_claims.HTTPHopResponse(
            status_code=302,
            location="https://cdn.example/article.pdf",
            content_type="text/html",
            content=b"",
        )

    return academic_claims.HTTPHopResponse(
        status_code=200,
        location=None,
        content_type="application/pdf",
        content=b"redirected-pdf",
    )


socket.getaddrinfo = redirect_getaddrinfo

try:
    redirected_download = academic_claims.download_validated_http_source(
        "https://journal.example/article",
        requester=redirect_requester,
    )
finally:
    socket.getaddrinfo = original_getaddrinfo


assert redirected_download.content == b"redirected-pdf"
assert redirect_dns_calls == [
    ("journal.example", 0),
    ("cdn.example", 0),
]
assert redirect_requests == [
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


# Unsafe or unusable DNS results must fail before requester invocation.
dns_failure_cases = [
    ("private", ["127.0.0.1"], None),
    ("mixed", ["8.8.8.8", "127.0.0.1"], None),
    ("empty", [], None),
    ("failure", None, socket.gaierror("synthetic DNS failure")),
]

for case_name, addresses, dns_error in dns_failure_cases:
    requester_called = []

    def boundary_getaddrinfo(host, port, *args, **kwargs):
        if dns_error is not None:
            raise dns_error

        return [
            make_dns_record(address, port)
            for address in addresses
        ]

    def boundary_requester(url, destination):
        requester_called.append((url, destination))
        raise AssertionError(
            f"{case_name}: unsafe destination reached requester"
        )

    socket.getaddrinfo = boundary_getaddrinfo

    try:
        try:
            academic_claims.download_validated_http_source(
                "https://journal.example/article.pdf",
                requester=boundary_requester,
            )
        except academic_claims.SourceRetrievalError:
            pass
        else:
            raise AssertionError(
                f"{case_name}: expected SourceRetrievalError"
            )
    finally:
        socket.getaddrinfo = original_getaddrinfo

    assert requester_called == [], (
        f"{case_name}: requester must not run before safe DNS validation"
    )


print("PASS: redirect hostname is independently resolved and validated")
print("PASS: private DNS answer is rejected before transport")
print("PASS: mixed public/private DNS answer is rejected before transport")
print("PASS: empty DNS answer is rejected before transport")
print("PASS: DNS resolution failure becomes SourceRetrievalError")
