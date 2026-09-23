#!/usr/bin/env python3
"""Regression test for a scholarly HTTP source that stalls mid-response."""

import socket
import sys
import threading
import time
from pathlib import Path

import httpcore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import academic_claims


print("\n[1] stalled HTTP body is bounded by production timeout")


client_socket, server_socket = socket.socketpair()
original_connect_tcp = httpcore.SyncBackend.connect_tcp

observed_connect_timeouts = []
server_finished = threading.Event()


def fake_connect_tcp(
    self,
    host,
    port,
    timeout=None,
    local_address=None,
    socket_options=None,
):
    assert host == "8.8.8.8"
    assert port == 80

    observed_connect_timeouts.append(timeout)

    return httpcore._backends.sync.SyncStream(client_socket)


def stalled_server():
    try:
        request = b""

        while b"\r\n\r\n" not in request:
            chunk = server_socket.recv(4096)

            if not chunk:
                return

            request += chunk

        server_socket.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Length: 100\r\n"
            b"\r\n"
            b"%PDF-"
        )

        # Deliberately leave the connection open beyond the retrieval budget.
        time.sleep(1.0)
    finally:
        try:
            server_socket.close()
        finally:
            server_finished.set()


server_thread = threading.Thread(
    target=stalled_server,
    daemon=True,
)

server_thread.start()

started = time.monotonic()

try:
    httpcore.SyncBackend.connect_tcp = fake_connect_tcp

    try:
        academic_claims.download_validated_http_source(
            "http://journal.example/article.pdf",
            resolver=lambda hostname: ["8.8.8.8"],
            timeout=0.15,
        )
    except academic_claims.SourceRetrievalError:
        pass
    else:
        raise AssertionError(
            "Stalled HTTP body must become SourceRetrievalError."
        )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp

elapsed = time.monotonic() - started

server_thread.join(timeout=2.0)

assert observed_connect_timeouts
assert observed_connect_timeouts[0] is not None
assert 0 < observed_connect_timeouts[0] <= 0.15

assert elapsed < 0.75, (
    f"Stalled retrieval exceeded expected timeout bound: {elapsed:.3f}s"
)

assert not server_thread.is_alive()
assert server_finished.is_set()

print("PASS: production request configures a finite socket timeout")
print(f"PASS: stalled body returned after {elapsed:.3f}s")
print("PASS: stalled retrieval becomes controlled SourceRetrievalError")
print("PASS: socket/connection cleanup releases the peer")


print("\nAll stalled scholarly-source timeout checks passed.")
