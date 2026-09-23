#!/usr/bin/env python3
"""Regression tests for bounded scholarly-source HTTP retrieval."""

import sys
from pathlib import Path

import httpcore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import academic_claims


print("\n[1] HTTP hop configures finite transport timeouts")


captured_requests = []
response_closed = []
connection_closed = []


class ImmediateResponse:
    status = 200
    headers = [
        (b"content-type", b"application/pdf"),
    ]

    def iter_stream(self):
        yield b"pdf-content"

    def close(self):
        response_closed.append(True)


class RecordingConnection:
    def __init__(self, origin, network_backend, http1, http2):
        pass

    def handle_request(self, request):
        captured_requests.append(request)
        return ImmediateResponse()

    def close(self):
        connection_closed.append(True)


destination = academic_claims.ValidatedHTTPDestination(
    hostname="journal.example",
    addresses=["8.8.8.8"],
)

academic_claims.request_validated_http_hop(
    "https://journal.example/article.pdf",
    destination=destination,
    connection_factory=RecordingConnection,
    deadline=105.0,
    monotonic=lambda: 100.0,
)

assert len(captured_requests) == 1

timeouts = captured_requests[0].extensions["timeout"]

for timeout_name in ("connect", "read", "write", "pool"):
    assert timeout_name in timeouts
    assert timeouts[timeout_name] is not None
    assert 0 < timeouts[timeout_name] <= 5.0

assert response_closed == [True]
assert connection_closed == [True]

print("PASS: connect/read/write/pool receive finite remaining-budget timeouts")
print("PASS: successful response and connection are closed")


print("\n[2] expired deadline prevents a new HTTP hop")


expired_connections = []


class ForbiddenConnection:
    def __init__(self, origin, network_backend, http1, http2):
        expired_connections.append(True)
        raise AssertionError("Expired request must not create a connection.")


try:
    academic_claims.request_validated_http_hop(
        "https://journal.example/article.pdf",
        destination=destination,
        connection_factory=ForbiddenConnection,
        deadline=100.0,
        monotonic=lambda: 100.0,
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError("Expired HTTP deadline must fail retrieval.")

assert expired_connections == []

print("PASS: expired deadline is rejected before opening a connection")


print("\n[3] downloader carries one deadline across redirects")


clock = [100.0]
observed_request_times = []


def resolver(hostname):
    if hostname == "journal.example":
        return ["8.8.8.8"]

    if hostname == "cdn.example":
        return ["1.1.1.1"]

    raise AssertionError(f"Unexpected hostname: {hostname}")


def deadline_requester(url, destination):
    observed_request_times.append(clock[0])

    if url == "https://journal.example/start":
        clock[0] += 2.0
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
            content_type="application/pdf",
            content=b"pdf-content",
        )

    raise AssertionError(f"Unexpected URL: {url}")


downloaded = academic_claims.download_validated_http_source(
    "https://journal.example/start",
    requester=deadline_requester,
    resolver=resolver,
    timeout=5.0,
    monotonic=lambda: clock[0],
)

assert downloaded.content == b"pdf-content"
assert observed_request_times == [100.0, 102.0]

print("PASS: redirects proceed within one absolute retrieval deadline")
print("PASS: injected requesters retain the two-argument contract")


print("\n[3b] redirect cannot start after total deadline expires")


expired_redirect_calls = []


def expiring_requester(url, destination):
    expired_redirect_calls.append(url)

    if url == "https://journal.example/start":
        clock[0] = 106.0
        return academic_claims.HTTPHopResponse(
            status_code=302,
            location="https://cdn.example/article.pdf",
            content_type=None,
            content=b"",
        )

    raise AssertionError("Expired redirect must not invoke another requester.")


clock[0] = 100.0

try:
    academic_claims.download_validated_http_source(
        "https://journal.example/start",
        requester=expiring_requester,
        resolver=resolver,
        timeout=5.0,
        monotonic=lambda: clock[0],
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Redirect after the absolute deadline must fail retrieval."
    )

assert expired_redirect_calls == ["https://journal.example/start"]

print("PASS: expired redirect is stopped before another HTTP hop")


print("\nAll scholarly-source HTTP deadline contract checks passed.")


print("\n[4] trickled response cannot outlive absolute deadline")


trickle_clock = [100.0]
trickle_response_closed = []
trickle_connection_closed = []


class TricklingResponse:
    status = 200
    headers = [
        (b"content-type", b"application/pdf"),
    ]

    def iter_stream(self):
        trickle_clock[0] = 101.0
        yield b"first"

        trickle_clock[0] = 103.0
        yield b"second"

        trickle_clock[0] = 106.0
        yield b"third"

    def close(self):
        trickle_response_closed.append(True)


class TricklingConnection:
    def __init__(self, origin, network_backend, http1, http2):
        pass

    def handle_request(self, request):
        return TricklingResponse()

    def close(self):
        trickle_connection_closed.append(True)


try:
    academic_claims.request_validated_http_hop(
        "https://journal.example/article.pdf",
        destination=destination,
        connection_factory=TricklingConnection,
        deadline=105.0,
        monotonic=lambda: trickle_clock[0],
    )
except academic_claims.SourceRetrievalError:
    pass
else:
    raise AssertionError(
        "Trickled body must not continue beyond the absolute retrieval deadline."
    )

assert trickle_response_closed == [True]
assert trickle_connection_closed == [True]

print("PASS: absolute deadline stops a trickled response")
print("PASS: timed-out response and connection are closed")
