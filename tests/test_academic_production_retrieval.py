#!/usr/bin/env python3
"""Integration regression for production scholarly PDF retrieval."""

import socket
import sys
from io import BytesIO
from pathlib import Path

import httpcore
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app import academic_claims
import server


def add_text_page(writer, text):
    page = writer.add_blank_page(width=612, height=792)

    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")

    fonts = DictionaryObject()
    fonts[NameObject("/F1")] = font

    resources = DictionaryObject()
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources

    escaped = (
        text
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )

    stream = DecodedStreamObject()
    stream.set_data(
        (
            "BT\n"
            "/F1 12 Tf\n"
            "72 720 Td\n"
            f"({escaped}) Tj\n"
            "ET\n"
        ).encode("ascii")
    )

    page[NameObject("/Contents")] = stream


def make_test_pdf():
    writer = PdfWriter()
    add_text_page(
        writer,
        "Synthetic scholarly introduction.",
    )
    add_text_page(
        writer,
        "Results show mean jump height increased by 2.4 cm.",
    )

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class PDFStream:
    def __init__(self, response, writes):
        self.response = response
        self.writes = writes
        self.offset = 0

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


print("\n[1] server production path retrieves hostname PDF")

pdf_bytes = make_test_pdf()
dns_calls = []
tcp_destinations = []
request_writes = []

original_getaddrinfo = socket.getaddrinfo
original_connect_tcp = httpcore.SyncBackend.connect_tcp


def test_getaddrinfo(host, port, *args, **kwargs):
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


def test_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    tcp_destinations.append((host, port))

    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/pdf\r\n"
        + f"Content-Length: {len(pdf_bytes)}\r\n".encode("ascii")
        + b"\r\n"
        + pdf_bytes
    )

    return PDFStream(response, request_writes)


location = academic_claims.SourceLocation(
    status="location_found",
    doi="10.1234/production-retrieval",
    source="openalex",
    landing_page_url=None,
    pdf_url="https://journal.example/article.pdf",
    is_oa=True,
    reasons=["Synthetic source location."],
)

try:
    socket.getaddrinfo = test_getaddrinfo
    httpcore.SyncBackend.connect_tcp = test_connect_tcp

    retrieved = server.retrieve_academic_source(location)
finally:
    socket.getaddrinfo = original_getaddrinfo
    httpcore.SyncBackend.connect_tcp = original_connect_tcp


assert dns_calls == [
    ("journal.example", 0),
]

assert tcp_destinations == [
    ("8.8.8.8", 443),
]

request_bytes = b"".join(request_writes)

assert b"GET /article.pdf HTTP/1.1\r\n" in request_bytes
assert request_bytes.count(
    b"Host: journal.example\r\n"
) == 1

assert retrieved.status == "retrieved"
assert retrieved.doi == "10.1234/production-retrieval"
assert retrieved.source == "openalex"
assert retrieved.locator == "https://journal.example/article.pdf"

assert retrieved.text == (
    "Synthetic scholarly introduction.\n\n"
    "Results show mean jump height increased by 2.4 cm."
)

assert len(retrieved.pages) == 2

assert retrieved.pages[0].page_number == 1
assert retrieved.pages[0].text == (
    "Synthetic scholarly introduction."
)

assert retrieved.pages[1].page_number == 2
assert "2.4 cm" in retrieved.pages[1].text

print("PASS: server uses production PDF retrieval without injected downloader")
print("PASS: production downloader resolves hostname through system DNS")
print("PASS: validated public IP is the TCP destination")
print("PASS: original hostname remains the HTTP Host authority")
print("PASS: real HTTP response supplies a valid PDF")
print("PASS: real PdfReader extracts substantive text")
print("PASS: retrieval preserves one-based physical page provenance")
