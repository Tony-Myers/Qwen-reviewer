#!/usr/bin/env python3
"""
Do the citations in a chat probe file exist? Resolve them against Crossref.

Section 12 records seven citation defects and separates them into three kinds:
metadata wrong, source real but cited for something it does not say, and source
invented. Only the first two were established with confidence. "Cannot be
placed" was as far as an offline reading could go, so the split between
fabricated and real-but-misattributed is still an estimate -- and that split is
what the registry design turns on. A registry fixes wrong metadata completely,
fixes fabrication completely, and fixes misattribution not at all.

This resolves the first question mechanically. It does not touch the second:
whether a real paper says what it was cited for cannot be settled by a lookup.

    python3 tests/probe_resolve_citations.py logs/chat-citations-*.md

Run it on the machine with network access. Crossref is queried by
bibliographic string, three candidates each, and any DOI in the claim is
resolved directly as well.

TWO THINGS TO KNOW BEFORE READING THE OUTPUT.

Crossref indexes journal articles well and books poorly. Cohen (1988),
Borenstein et al. (2009) and Kruschke (2015) are books, and an unresolved book
is not evidence of anything. They are marked as such and excluded from the
count.

A close title match means the paper exists. It does not mean the claimed
authors, year, volume or pages were right -- those are printed beside it so
the difference is visible, which is the metadata check of section 12.3 done
mechanically rather than by eye.
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

CROSSREF = "https://api.crossref.org/works"
MAILTO = "admyers@aol.com"          # Crossref asks for a contact; be polite
ROWS = 3
PAUSE = 0.4                         # courtesy between queries

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s)\]\"'>,;]+)")
YEAR_RE = re.compile(r"\((\d{4})[a-z]?\)")
BOOKISH = re.compile(
    r"\b(Wiley|Erlbaum|Academic Press|Chapman|CRC|Springer|Sage|Routledge|"
    r"Cambridge University|Oxford University|Guilford|Handbook|\(\d+(?:st|nd|rd|th) ed\.?\))",
    re.I)


# A reference entry, not a sentence that happens to contain a year. The first
# version of this took any line with a year and forty-five characters, and half
# of what it extracted was prose -- "This recommendation has been widely
# adopted... Later work, such as..." -- which then returned no Crossref match
# and was counted as an unresolved reference. Fifty-five unresolved was not a
# fabrication count, it was mostly narrative.
AUTHOR_START = re.compile(
    r"^(?:\d+\.\s*)?[A-Z][A-Za-z'\u2019-]+,\s*[A-Z]\.")      # Cohen, J.
AUTHOR_AMP = re.compile(
    r"^(?:\d+\.\s*)?[A-Z][A-Za-z'\u2019-]+(?:,\s*[A-Z]\.)?(?:,|\s*&|\s+and\s+)"
    r"\s*[A-Z][A-Za-z'\u2019-]+")                              # Hartung & Knapp
VOL_PAGES = re.compile(r"\b\d{1,3}\(\d{1,3}\),?\s*\d{1,4}[-\u2013]\d{1,4}")


def candidate_references(answer: str):
    """Lines shaped like a reference entry."""
    out = []
    for raw in answer.splitlines():
        line = re.sub(r"[*_`>#]", "", raw).strip(" -\u2013\t")
        if len(line) < 45:
            continue
        if not (YEAR_RE.search(line) or DOI_RE.search(line)):
            continue
        looks_like_entry = (DOI_RE.search(line)
                            or VOL_PAGES.search(line)
                            or AUTHOR_START.match(line)
                            or AUTHOR_AMP.match(line))
        if not looks_like_entry:
            continue
        # a bare in-text mention carries no title
        after = YEAR_RE.split(line)[-1] if YEAR_RE.search(line) else line
        if len(after.split()) < 4 and not DOI_RE.search(line):
            continue
        out.append(line)
    return out


def crossref(query: str, rows: int = ROWS):
    url = (f"{CROSSREF}?rows={rows}&mailto={urllib.parse.quote(MAILTO)}"
           f"&query.bibliographic={urllib.parse.quote(query[:400])}")
    req = urllib.request.Request(url, headers={"User-Agent": f"qwen-review-probe ({MAILTO})"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))["message"].get("items", [])


def by_doi(doi: str):
    url = f"{CROSSREF}/{urllib.parse.quote(doi)}?mailto={urllib.parse.quote(MAILTO)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"qwen-review-probe ({MAILTO})"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))["message"]
    except Exception:
        return None


def describe(item):
    title = (item.get("title") or ["(no title)"])[0]
    authors = item.get("author") or []
    who = ", ".join(a.get("family", "?") for a in authors[:3]) or "(no authors)"
    if len(authors) > 3:
        who += " et al."
    year = ""
    for key in ("issued", "published-print", "published-online"):
        parts = (item.get(key) or {}).get("date-parts") or [[]]
        if parts and parts[0]:
            year = str(parts[0][0])
            break
    venue = (item.get("container-title") or [""])[0]
    return title, who, year, venue, item.get("DOI", "")


def claimed_title(ref: str) -> str:
    """The title as claimed, not the whole entry.

    Comparing a returned title with the entire claim -- authors, year, journal,
    volume, pages and all -- drags the ratio down and marks correct citations
    as unmatched. Cohen (1992), "A power primer", Psychological Bulletin came
    back from Crossref as exactly itself and scored 0.36 against the full line.
    """
    quoted = re.findall(r"[\"\u201c]([^\"\u201d]{12,})[\"\u201d]", ref)
    if quoted:
        return max(quoted, key=len)
    after = YEAR_RE.split(ref)[-1] if YEAR_RE.search(ref) else ref
    after = after.lstrip(" .:)")
    venueish = re.compile(r"\d{1,3}\(\d|\d+\s*[-\u2013]\s*\d+|doi|https?://", re.I)
    for chunk in re.split(r"\.\s+|\.$", after):
        chunk = chunk.strip()
        if len(chunk.split()) >= 2 and not venueish.search(chunk):
            return chunk
    return after.strip()


def similarity(a: str, b: str) -> float:
    """Title against claimed title."""
    norm = lambda s: re.sub(r"[^a-z0-9 ]", " ", s.lower()).split()
    return SequenceMatcher(None, " ".join(norm(a)),
                           " ".join(norm(claimed_title(b)))).ratio()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 0
    resolved = unresolved = books = 0
    report = ["# Citation resolution", ""]

    for path in sys.argv[1:]:
        text = Path(path).read_text(encoding="utf-8")
        report += [f"## {Path(path).name}", ""]
        blocks = re.split(r"^## \d+\. ", text, flags=re.M)[1:]
        for i, block in enumerate(blocks, 1):
            question = block.splitlines()[0]
            refs = candidate_references(block)
            if not refs:
                continue
            report += [f"### Q{i}. {question}", ""]
            for ref in refs:
                claimed_doi = DOI_RE.search(ref)
                line = [f"- **claimed:** {ref[:220]}"]
                if BOOKISH.search(ref) and not claimed_doi:
                    books += 1
                    line.append("  - *book or edited volume; Crossref coverage "
                                "is poor here, not counted*")
                    report += line + [""]
                    continue
                try:
                    if claimed_doi:
                        item = by_doi(claimed_doi.group(1))
                        if item is None:
                            unresolved += 1
                            line.append(f"  - **DOI {claimed_doi.group(1)} does "
                                        "not resolve**")
                            report += line + [""]
                            continue
                        t, who, yr, venue, doi = describe(item)
                        line.append(f"  - DOI resolves to: {who} ({yr}). {t}. {venue}.")
                        line.append(f"  - title similarity to the claim: "
                                    f"{similarity(t, ref):.2f}")
                        resolved += 1
                    else:
                        items = crossref(ref)
                        time.sleep(PAUSE)
                        if not items:
                            unresolved += 1
                            line.append("  - **no Crossref match**")
                            report += line + [""]
                            continue
                        best = max(items, key=lambda it: similarity(
                            (it.get("title") or [""])[0], ref))
                        t, who, yr, venue, doi = describe(best)
                        s = similarity(t, ref)
                        # Title against title is a much sharper comparison
                        # than title against the whole entry, so the threshold
                        # rises with it: correct citations now score at or near
                        # 1.00, while the invented Hartung-Knapp-Sidik paper
                        # scores 0.54 against a real paper on the same subject.
                        verdict = ("looks like the same work" if s > 0.70
                                   else "**no close match — check by hand**")
                        if s <= 0.70:
                            unresolved += 1
                        else:
                            resolved += 1
                        line.append(f"  - closest: {who} ({yr}). {t}. {venue}. {doi}")
                        line.append(f"  - title similarity {s:.2f} — {verdict}")
                except Exception as exc:
                    line.append(f"  - lookup failed: {exc}")
                report += line + [""]

    report += ["", f"**Resolved: {resolved}. No close match: {unresolved}. "
               f"Books excluded: {books}.**", "",
               "A resolved citation may still be cited for a claim its source "
               "does not make. That check is not mechanical and is not done "
               "here."]
    out = Path("logs") / f"citation-resolution-{time.strftime('%Y%m%d-%H%M%S')}.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report[-4:]))
    print(f"\nWritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
