#!/usr/bin/env python3
"""Regression test for a scholarly HTTP source that trickles then stalls."""

import socket
import sys
import threading
import time
from pathlib import Path

import httpcore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import academic_claims


print("\n[1] trickling HTTP body must respect the absolute retrieval deadline")


client_socket, server_socket = socket.socketpair()
original_connect_tcp = httpcore.SyncBackend.connect_tcp

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

    return httpcore._backends.sync.SyncStream(client_socket)


def trickling_server():
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

        # Keep the connection active for most of the total budget.
        time.sleep(0.10)
        server_socket.sendall(b"trickle")

        # Now stall. A per-read timeout fixed at the original 0.20 s
        # permits this read to continue well beyond the absolute deadline.
        time.sleep(0.30)

    except (BrokenPipeError, ConnectionResetError):
        # Expected once the client enforces the total deadline and closes.
        pass
    finally:
        try:
            server_socket.close()
        finally:
            server_finished.set()


server_thread = threading.Thread(
    target=trickling_server,
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
            timeout=0.20,
        )
    except academic_claims.SourceRetrievalError:
        pass
    else:
        raise AssertionError(
            "Trickling HTTP body must become SourceRetrievalError."
        )
finally:
    httpcore.SyncBackend.connect_tcp = original_connect_tcp

elapsed = time.monotonic() - started

server_thread.join(timeout=2.0)

print(f"Observed retrieval time: {elapsed:.3f}s")

# Allow scheduling tolerance, but not another complete 0.20 s idle timeout
# after the server's 0.10 s trickle.
assert elapsed < 0.27, (
    "Trickled retrieval exceeded the absolute deadline: "
    f"{elapsed:.3f}s"
)

assert not server_thread.is_alive()
assert server_finished.is_set()

print("PASS: trickle cannot reset or extend the total retrieval budget")
print("PASS: timed-out connection releases the peer")


print("\nAll scholarly-source trickle deadline checks passed.")
