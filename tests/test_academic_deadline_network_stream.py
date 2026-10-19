#!/usr/bin/env python3
"""Contract tests for the deadline-aware scholarly HTTP network stream."""

import sys
from pathlib import Path

import httpcore

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import academic_claims


class RecordingStream:
    def __init__(self):
        self.read_timeouts = []
        self.write_timeouts = []
        self.tls_timeouts = []
        self.closed = False
        self.extra_info = {"socket": "sentinel-socket"}
        self.tls_stream = None

    def read(self, max_bytes, timeout=None):
        self.read_timeouts.append(timeout)
        return b"x" * min(max_bytes, 1)

    def write(self, buffer, timeout=None):
        self.write_timeouts.append(timeout)

    def close(self):
        self.closed = True

    def start_tls(
        self,
        ssl_context,
        server_hostname=None,
        timeout=None,
    ):
        self.tls_timeouts.append(timeout)
        self.tls_stream = RecordingStream()
        return self.tls_stream

    def get_extra_info(self, info):
        return self.extra_info.get(info)


print("\n[1] read and write use the remaining absolute budget")

clock = [100.0]
underlying = RecordingStream()

stream = academic_claims.DeadlineNetworkStream(
    underlying,
    deadline=105.0,
    monotonic=lambda: clock[0],
)

assert stream.read(10, timeout=20.0) == b"x"
assert underlying.read_timeouts == [5.0]

clock[0] = 102.0
stream.write(b"abc", timeout=20.0)
assert underlying.write_timeouts == [3.0]

clock[0] = 103.0
stream.read(10, timeout=0.5)
assert underlying.read_timeouts[-1] == 0.5

print("PASS: read/write timeouts are capped by remaining deadline")
print("PASS: a shorter caller timeout remains shorter")


print("\n[2] TLS upgrade preserves the same absolute deadline")

clock[0] = 103.0

tls_stream = stream.start_tls(
    ssl_context=object(),
    server_hostname="journal.example",
    timeout=20.0,
)

assert underlying.tls_timeouts == [2.0]
assert isinstance(tls_stream, academic_claims.DeadlineNetworkStream)

clock[0] = 104.0
assert tls_stream.read(10, timeout=20.0) == b"x"
assert underlying.tls_stream.read_timeouts == [1.0]

print("PASS: TLS handshake receives only the remaining budget")
print("PASS: upgraded TLS stream retains the original deadline")


print("\n[3] close and get_extra_info delegate to the underlying stream")

assert stream.get_extra_info("socket") == "sentinel-socket"
stream.close()
assert underlying.closed

print("PASS: stream metadata and close behaviour are preserved")


print("\n[4] expired deadline blocks underlying network operations")

expired_clock = [105.0]
expired_underlying = RecordingStream()

expired_stream = academic_claims.DeadlineNetworkStream(
    expired_underlying,
    deadline=105.0,
    monotonic=lambda: expired_clock[0],
)

for operation in (
    lambda: expired_stream.read(10, timeout=5.0),
    lambda: expired_stream.write(b"x", timeout=5.0),
    lambda: expired_stream.start_tls(
        ssl_context=object(),
        server_hostname="journal.example",
        timeout=5.0,
    ),
):
    try:
        operation()
    except httpcore.TimeoutException:
        pass
    else:
        raise AssertionError(
            "Expired deadline must prevent the underlying network operation."
        )

assert expired_underlying.read_timeouts == []
assert expired_underlying.write_timeouts == []
assert expired_underlying.tls_timeouts == []

print("PASS: expired deadline prevents read/write/TLS operations")


print("\nAll deadline-aware network stream contract checks passed.")
