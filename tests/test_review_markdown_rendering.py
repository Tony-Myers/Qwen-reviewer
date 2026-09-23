#!/usr/bin/env python3
"""Regression checks for safe Markdown rendering on review surfaces."""

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
    r"function\s+renderMd\s*\(\s*md\s*\)\s*\{(?P<body>.*?)\n\}",
    source,
    flags=re.DOTALL,
)

check("review Markdown renderer is present", match is not None)
body = match.group("body") if match else ""

print("\n[review Markdown is escaped before rendering]")

escape_call = re.search(r"\bh\s*=\s*esc\s*\(\s*md\s*\)", body)
first_replace = re.search(r"\bh\s*=\s*h\.replace\s*\(", body)

check(
    "complete review Markdown is escaped",
    escape_call is not None,
    body.strip(),
)

check(
    "escaping occurs before the first Markdown replacement",
    escape_call is not None
    and (first_replace is None or escape_call.start() < first_replace.start()),
    body.strip(),
)

print("\n[review surfaces use renderMd]")

check(
    "completed report is rendered through renderMd",
    "renderMd(md)" in source,
)

check(
    "review answers are rendered through renderMd",
    "renderMd(d.answer + '\\n' + (d.check || ''))" in source,
)

check(
    "evidence appendix is rendered through renderMd",
    re.search(
        r"sec\.innerHTML\s*=\s*'<div class=\"report-content\">'\s*\+\s*renderMd\(md\)",
        source,
    ) is not None,
)

print("\n[unordered Markdown lists]")

# The active review pipeline programmatically emits "- " bullets. Model output
# may also legitimately use either conventional unordered-list marker. The
# review renderer therefore has to recognise both "-" and "*".
bullet_rule = re.search(
    r"replace\(/\^\\s\*\[\*-\]\\s\+\(\.\+\)\$/gm,\s*'<li>\$1</li>'\)",
    body,
)

check(
    "renderer accepts both '-' and '*' unordered-list markers",
    bullet_rule is not None,
    "Expected a rule equivalent to h.replace(/^\\s*[*-]\\s+(.+)$/gm, '<li>$1</li>')",
)

check(
    "rendered list items are grouped into an unordered list",
    re.search(
        r"h\.replace\(/\(<li>\[\\s\\S\]\*\?<\\/li>\\n\?\)\+/g,\s*m\s*=>\s*'<ul>'\s*\+\s*m\s*\+\s*'</ul>'\)",
        body,
    ) is not None,
    body.strip(),
)

print("\n[fenced evidence blocks]")

check(
    "renderer converts fenced blocks to preformatted code",
    "'<pre><code>'" in body and "'</code></pre>'" in body,
    body.strip(),
)

check(
    "report preformatted blocks scroll horizontally",
    re.search(
        r"\.report-content\s+pre\s*\{[^}]*overflow-x\s*:\s*auto\s*;",
        source,
        re.DOTALL,
    ) is not None,
    "Evidence appendices contain long extracted tables inside fenced text blocks.",
)

check(
    "report preformatted blocks have dedicated block styling",
    re.search(
        r"\.report-content\s+pre\s*\{[^}]*(?:padding|border)\s*:",
        source,
        re.DOTALL,
    ) is not None,
    "Inline code styling alone is insufficient for appendix table and manifest blocks.",
)

if fails:
    print(f"\nFAILED: {len(fails)} check(s)")
    raise SystemExit(1)

print("\nPASS: review Markdown rendering is safe and supports its unordered-list contract")
