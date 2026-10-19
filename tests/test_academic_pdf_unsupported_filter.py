#!/usr/bin/env python3
"""Regression for real pypdf unsupported-filter extraction failure."""

import socket
import sys
from io import BytesIO
from pathlib import Path

import httpcore
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    NameObject,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app import academic_claims
import server


def make_unsupported_filter_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 72 720 Td (Unsupported filter test) Tj ET"
    )
    stream[NameObject("/Filter")] = NameObject("/UnsupportedFilter")
    page[NameObject("/Contents")] = stream

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class PDFStream:
    def __init__(self, response):
        self.response = response
        self.offset = 0
        self.writes = []

    def write(self, buffer, timeout=None):
        self.writes.append(bytes(buffer))

    def read(self, max_bytes, timeout=None):
        if self.offset >= len(self.response):
            return b""

        chunk = self.response[
            self.offset:self.offset + max_bytes
        ]
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


print(
    "\n[1] unsupported PDF filter is contained by "
    "production source retrieval"
)

pdf_bytes = make_unsupported_filter_pdf()

response = (
    b"HTTP/1.1 200 OK\r\n"
    b"Content-Type: application/pdf\r\n"
    + f"Content-Length: {len(pdf_bytes)}\r\n".encode("ascii")
    + b"Connection: close\r\n"
    b"\r\n"
    + pdf_bytes
)

dns_calls = []
tcp_destinations = []

original_getaddrinfo = socket.getaddrinfo
original_connect_tcp = httpcore.SyncBackend.connect_tcp


def fake_getaddrinfo(host, port, *args, **kwargs):
    dns_calls.append((host, port))

    assert host == "journal.example"

    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("8.8.8.8", port),
        ),
    ]


def fake_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    tcp_destinations.append((host, port))
    return PDFStream(response)


location = academic_claims.SourceLocation(
    status="location_found",
    doi="10.1234/unsupported-filter",
    source="openalex",
    landing_page_url=None,
    pdf_url="https://journal.example/unsupported.pdf",
    is_oa=True,
    reasons=["Synthetic unsupported-filter source."],
)

try:
    socket.getaddrinfo = fake_getaddrinfo
    httpcore.SyncBackend.connect_tcp = fake_connect_tcp

    retrieved = server.retrieve_academic_source(location)
finally:
    socket.getaddrinfo = original_getaddrinfo
    httpcore.SyncBackend.connect_tcp = original_connect_tcp


assert dns_calls == [("journal.example", 0)]
assert tcp_destinations == [("8.8.8.8", 443)]

assert retrieved.status == "not_retrieved"
assert retrieved.doi == "10.1234/unsupported-filter"
assert retrieved.source == "openalex"
assert retrieved.text is None
assert retrieved.locator is None
assert retrieved.pages is None
assert retrieved.reasons == ["Source text extraction failed."]

print("PASS: unsupported pypdf filter becomes controlled retrieval failure")
print("PASS: bibliographic identity survives extraction failure")
print("PASS: failed extraction invents no source text, locator, or pages")
print("PASS: validated numeric TCP destination remains unchanged")

print("\nAll unsupported-filter PDF checks passed.")


print("\n[2] unrelated NotImplementedError remains visible")


class UnexpectedPage:
    def extract_text(self):
        raise NotImplementedError("synthetic programming limitation")


class UnexpectedReader:
    def __init__(self, stream):
        self.pages = [UnexpectedPage()]


try:
    academic_claims.extract_pdf_pages(
        b"%PDF-synthetic",
        reader_factory=UnexpectedReader,
    )
except NotImplementedError as exc:
    assert str(exc) == "synthetic programming limitation"
else:
    raise AssertionError(
        "Unrecognised NotImplementedError should propagate unchanged."
    )

print("PASS: unrelated NotImplementedError propagates unchanged")
print("PASS: unsupported-filter containment remains narrowly classified")
