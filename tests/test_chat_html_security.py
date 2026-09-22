#!/usr/bin/env python3
"""Static regression checks for hostile HTML in chat rendering."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAT = ROOT / "app" / "chat.html"
source = CHAT.read_text(encoding="utf-8")

fails = []


def check(label, condition, detail=None):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        if detail is not None:
            print(f"        {detail}")
        fails.append(label)


match = re.search(
    r"function\s+fmtMd\s*\(\s*t\s*\)\s*\{(?P<body>.*?)\n\}",
    source,
    flags=re.DOTALL,
)

check(
    "fmtMd function is present",
    match is not None,
)

body = match.group("body") if match else ""

# Security invariant: untrusted chat text must be HTML-escaped before the
# renderer introduces its own controlled markup.  Escaping only code-block
# contents is insufficient because ordinary user/model text reaches innerHTML.
escape_call = re.search(r"\bt\s*=\s*esc\s*\(\s*t\s*\)", body)
first_replace = re.search(r"\bt\s*=\s*t\.replace\s*\(", body)

check(
    "complete chat text is escaped before Markdown rendering",
    escape_call is not None,
    body.strip(),
)

check(
    "HTML escaping occurs before the first Markdown replacement",
    escape_call is not None
    and (first_replace is None or escape_call.start() < first_replace.start()),
    body.strip(),
)

check(
    "chat rendering still passes formatted content through fmtMd",
    "fmtMd(content)" in source,
)

# Document the hostile input this regression protects against.  It must not be
# possible for this client/model-controlled element to survive as raw markup.
hostile = '<img src=x onerror="alert(1)">'
escaped = "&lt;img src=x onerror=\"alert(1)\"&gt;"

check(
    "escape helper neutralises angle brackets used by hostile HTML",
    "replace(/</g,'&lt;')" in source
    and "replace(/>/g,'&gt;')" in source,
    f"{hostile!r} must render as text such as {escaped!r}",
)

if fails:
    print(f"\nFAILED: {len(fails)} check(s)")
    raise SystemExit(1)

print("\nPASS: chat text is escaped before controlled Markdown rendering")
