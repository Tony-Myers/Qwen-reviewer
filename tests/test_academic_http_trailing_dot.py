#!/usr/bin/env python3
"""Regression test for trailing-root-dot scholarly HTTP source URLs."""

import sys
from pathlib import Path

import httpcore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import academic_claims


class MemoryStream(httpcore.NetworkStream):
    def __init__(self, response_bytes):
        self._response = bytearray(response_bytes)
        self.writes = []
        self.closed = False
        self.tls_server_hostnames = []

    def read(self, max_bytes, timeout=None):
        if not self._response:
            return b""
        chunk = bytes(self._response[:max_bytes])
        del self._response[:max_bytes]
        return chunk

    def write(self, buffer, timeout=None):
        self.writes.append(bytes(buffer))

    def close(self):
        self.closed = True

    def start_tls(
        self,
        ssl_context,
        server_hostname=None,
        timeout=None,
    ):
        self.tls_server_hostnames.append(server_hostname)
        return self

    def get_extra_info(self, info):
        return None


print("\n[1] production HTTP path accepts equivalent trailing-dot hostname")

pdf_bytes = b"%PDF-1.4\ntrailing-dot-test\n"

response_bytes = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/pdf\r\n"
    + f"Content-Length: {len(pdf_bytes)}\r\n".encode("ascii")
    + b"Connection: close\r\n"
    b"\r\n"
    + pdf_bytes
)

stream = MemoryStream(response_bytes)
tcp_hosts = []

original_connect_tcp = httpcore.SyncBackend.connect_tcp


def fake_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    tcp_hosts.append(host)
    return stream


httpcore.SyncBackend.connect_tcp = fake_connect_tcp

try:
    result = academic_claims.download_validated_http_source(
        "https://journal.example./paper.pdf",
        resolver=lambda hostname: ["8.8.8.8"],
        timeout=1.0,
    )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp


assert result.content == pdf_bytes
assert result.requested_url == "https://journal.example./paper.pdf"
assert result.final_url == "https://journal.example./paper.pdf"

assert tcp_hosts == ["8.8.8.8"], (
    f"Expected validated numeric TCP destination, got {tcp_hosts!r}"
)

request_bytes = b"".join(stream.writes)

assert b"Host: journal.example\r\n" in request_bytes, request_bytes
assert b"GET /paper.pdf HTTP/1.1\r\n" in request_bytes, request_bytes
assert stream.tls_server_hostnames == ["journal.example"]

print("PASS: trailing-dot URL survives real httpcore origin validation")
print("PASS: HTTP Host uses canonical hostname")
print("PASS: TLS/SNI uses canonical hostname")
print("PASS: path is preserved")
print("PASS: TCP remains pinned to validated numeric address")


print("\n[2] redirect to trailing-dot hostname uses canonical transport identity")

first_response = (
    b"HTTP/1.1 302 Found\r\n"
    b"Location: https://cdn.example./paper.pdf?download=1\r\n"
    b"Content-Length: 0\r\n"
    b"Connection: close\r\n"
    b"\r\n"
)

second_pdf = b"%PDF-1.4\nredirect-trailing-dot-test\n"

second_response = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/pdf\r\n"
    + f"Content-Length: {len(second_pdf)}\r\n".encode("ascii")
    + b"Connection: close\r\n"
    b"\r\n"
    + second_pdf
)

redirect_streams = [
    MemoryStream(first_response),
    MemoryStream(second_response),
]
redirect_tcp_hosts = []
redirect_dns_calls = []

original_connect_tcp = httpcore.SyncBackend.connect_tcp


def redirect_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    redirect_tcp_hosts.append(host)

    if not redirect_streams:
        raise AssertionError("Unexpected additional TCP connection.")

    return redirect_streams.pop(0)


def redirect_resolver(hostname):
    redirect_dns_calls.append(hostname)

    addresses = {
        "journal.example": ["8.8.8.8"],
        "cdn.example": ["1.1.1.1"],
    }

    return addresses[hostname]


first_stream = redirect_streams[0]
second_stream = redirect_streams[1]

httpcore.SyncBackend.connect_tcp = redirect_connect_tcp

try:
    redirected = academic_claims.download_validated_http_source(
        "https://journal.example/start",
        resolver=redirect_resolver,
        timeout=1.0,
    )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp


assert redirected.content == second_pdf
assert redirected.requested_url == "https://journal.example/start"
assert (
    redirected.final_url
    == "https://cdn.example./paper.pdf?download=1"
)

assert redirect_dns_calls == [
    "journal.example",
    "cdn.example",
]

assert redirect_tcp_hosts == [
    "8.8.8.8",
    "1.1.1.1",
]

first_request = b"".join(first_stream.writes)
second_request = b"".join(second_stream.writes)

assert b"Host: journal.example\r\n" in first_request, first_request
assert b"GET /start HTTP/1.1\r\n" in first_request, first_request

assert b"Host: cdn.example\r\n" in second_request, second_request
assert (
    b"GET /paper.pdf?download=1 HTTP/1.1\r\n"
    in second_request
), second_request
assert first_stream.tls_server_hostnames == ["journal.example"]
assert second_stream.tls_server_hostnames == ["cdn.example"]

print("PASS: redirect trailing-dot hostname survives real httpcore validation")
print("PASS: redirected HTTP Host uses canonical hostname")
print("PASS: redirected TLS/SNI uses canonical hostname")
print("PASS: redirected path and query are preserved")
print("PASS: each redirect hostname is independently resolved")
print("PASS: each TCP hop uses only its independently validated numeric IP")
print("PASS: original trailing-dot redirect URL remains final provenance")

print("\nAll trailing-dot scholarly HTTP checks passed.")
