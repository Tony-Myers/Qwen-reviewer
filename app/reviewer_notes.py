#!/usr/bin/env python3
"""
Retrieval over the reviewer notes, for the chat.

A reviewer reading a finished report asks a question about how a statistic
should be reported or interpreted. This module returns passages from
`resources/reviewer_notes/` that bear on it. It does not answer the question
and it does not decide anything: the model answers, and these passages let the
reviewer check that answer against something written down.

Standard library only; no scikit-learn, so the review pipeline gains no
dependency and the index costs milliseconds to build.

It lives in app/ but is not one of the five files the pipeline fingerprint
covers, and deliberately so: it cannot change a report. A report is written by
the pipeline before any question is asked, and these passages reach only the
ask box. What does change a report's hash is server.py, which holds the prompt
and the provenance, and that is fingerprinted already.

    python3 tests/run_reviewer_notes.py "what convergence diagnostics are needed"

Four things measured in reports/CHAT-RETRIEVAL-PROBE.md decide the design.

1.  THE NOTES ONLY, NEVER THE TEXTBOOKS.
    On a whole-corpus index the textbooks supply about 92% of the chunks and
    outvote a five-chunk note on questions it should win: 11 of 21 in-scope
    questions answered, against 16 of 21 when retrieval is restricted to the
    notes (section 10). The restriction is the design, not an optimisation.

2.  PASSAGES ARE READING, NOT AN ANSWER, AND THE SCORE GATES NOTHING.
    No threshold reliably separates an answerable question from an
    unanswerable one, and the cost of a bad passage in chat is that the reader
    discards it (section 7.2). So passages are always shown, always labelled as
    possibly relevant, and never suppress or create a finding.

3.  CHUNK ON HEADINGS.
    A blind character window makes the retrieved passage begin part-way
    through the previous section, so the reviewer is shown the wrong paragraph
    even when the ranking is right (section 9.5).

4.  ALIAS EXACT TECHNICAL SYNONYMS ONLY.
    Expanding "R-hat" with "potential scale reduction factor PSRF" turns a
    complete miss into the defining passage. Expanding "WAIC or LOO" with the
    conceptual phrase "model comparison cross validation" made that question
    worse, because the added words belong to the prediction textbooks
    (section 7.3). Synonyms, never paraphrases.

5.  DEMOTE THE SECTIONS THAT DESCRIBE THE NOTE RATHER THAN ANSWER ANYTHING.
    A note's purpose, terminology list, red flags and checklists match many
    questions by word overlap and answer almost none of them; they were taking
    display slots from the sections carrying the explanation. Halving their
    score widened the gap between the in-scope and out-of-scope medians from
    0.127 to 0.153 over the fifty-one questions, and took the ten questions
    from a live review from eight to nine out of ten answered by a section
    that explains something. The result is flat for any weight at or below
    0.6, so this is the difference between demoting and not, rather than a
    tuned number.

    Two alternatives were measured against this one and rejected. Folding
    word forms together (sensitivity/sensitive) reached the right note more
    often and the right section less often, 8 of 10 down to 7, and narrowed
    the median gap to 0.106. Expanding a query about sensitivity with
    "robust" changed no ranking at all and lowered every score, because the
    added word lengthens the query vector without matching the passages that
    deserve to win. tests/probe_expansion.py reproduces all of it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

NOTES_DIR = Path(__file__).resolve().parent.parent / "resources" / "reviewer_notes"

CHUNK_CHARS = 1800
# A section shorter than this is merged into the one before it, so that bodies
# like "Incorrect." do not become passages in their own right. Everything else
# stands alone: one section, one passage, one citable heading. Packing small
# sections together was tried first and produced the right passage under the
# wrong heading -- the R-hat answer displayed as "What is Hamiltonian Monte
# Carlo?" -- which is the fault section 9.5 of the probe record exists to fix.
MIN_SECTION_CHARS = 220

# Headings whose sections describe the note instead of answering a question.
# "What reviewers should look for" is included because it is a checklist in
# substance -- the tick-list mirror of the box-list at the end -- and because
# it is the configuration the measurement in design note 5 was made under.
META_HEADINGS = (
    "purpose",
    "what reviewers should look for",
    "common reviewer questions",
    "common misconceptions",
    "common terminology",
    "common reviewer red flags",
    "quick reviewer checklist",
    "what this guide does",
)
META_WEIGHT = 0.5

_HEADING = re.compile(r"(?m)^\s{0,3}(#{1,6})\s+(\S.*)$")
_TOKEN = re.compile(r"[a-z0-9][a-z0-9_+-]*")

# sklearn's English list, trimmed to what actually occurs here. Kept explicit so
# the behaviour is inspectable rather than inherited from a library version.
_STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because
been before being below between both but by can cannot could did do does doing
down during each few for from further had has have having he her here hers him
his how i if in into is it its itself just me more most my no nor not now of
off on once only or other our out over own same she should so some such than
that the their them then there these they this those through to too under
until up very was we were what when where which while who whom why will with
would you your
""".split())

# Exact technical synonyms only. Adding a conceptual paraphrase here will make
# retrieval worse; see design note 4 above.
ALIASES: Dict[str, str] = {
    r"\br[\s-]?hat\b": "potential scale reduction factor psrf",
    r"\beffective sample size\b|\bess\b": "ess n_eff autocorrelation",
    r"\bpsrf\b": "r-hat potential scale reduction",
    r"\bcredible interval\b": "posterior interval",
    r"\beti\b": "equal-tailed interval",
    r"\b(hdi|hpdi)\b": "highest-density interval",
    r"\bpareto\s*k\b": "pareto k diagnostic",
    r"\bdivergent transitions?\b": "hmc divergences",
}


@dataclass
class Passage:
    note: str          # note title, from the file's first heading or its name
    heading: str       # the section heading this passage starts at
    text: str
    score: float

    def cite(self) -> str:
        return f"{self.note} - {self.heading}" if self.heading else self.note


# ---------------------------------------------------------------------------
# Curated references
# ---------------------------------------------------------------------------
# A note can carry checked references in fenced blocks:
#
#     ```references
#     - cite: Author, A. (2020). Title. Journal, 1(2), 3-4.
#       doi: 10.xxxx/yyyy
#       supports: What this source is listed for, in one sentence.
#       checked: 2026-09-30, Crossref
#     ```
#
# A block under a "References" heading is the note's list. A block anywhere
# else belongs to the section heading above it and replaces the note's list
# for that section, so a question about HDIs is not shown the note's sources
# on decision theory. Blocks are removed from the text before indexing: a
# reference list would otherwise add bibliographic words to the retrieval
# vectors and hand the judge a list of citations as though it were guidance.
#
# These are curated by hand and checked before they go in. The model never
# proposes them, which is the point: a reference the model supplies can be a
# real record attached to the wrong claim, or no record at all.

REFERENCE_KEYS = ("cite", "doi", "url", "isbn", "supports", "checked",
                  "short", "type", "access", "access_url", "access_checked")

# Access is recorded only from checked metadata (OpenAlex, or the hosting page
# read directly), never assumed. Absent means not checked, and nothing is
# shown to the reader for it.
ACCESS_LABELS = {
    "open": "Free to read",
    "repository": "Free copy in a repository",
    "author-copy": "Free copy from the authors",
    "subscription": "May need institutional access",
}
REFERENCES_HEADING = "references"

_REFERENCE_BLOCK = re.compile(
    r"(?ms)^```references[ \t]*\n(?P<body>.*?)^```[ \t]*$\n?")


class ReferenceFormatError(ValueError):
    """A references block that does not follow the curated format."""


_CITE_AUTHORS_YEAR = re.compile(r"^(?P<authors>.+?)\s*\((?P<year>\d{4}[a-z]?)\)")
_AUTHOR_BOUNDARY = re.compile(r"[A-Z]\.\s*,\s*(?=[A-Z\u00C0-\u017F])")


@dataclass
class Reference:
    cite: str
    supports: str
    doi: str = ""
    url: str = ""
    isbn: str = ""
    checked: str = ""
    short: str = ""
    type: str = ""
    access: str = ""
    access_url: str = ""
    access_checked: str = ""

    def link(self) -> str:
        """Where the reader can check the source: the DOI first, then a URL."""
        if self.doi:
            return "https://doi.org/" + self.doi
        return self.url

    def author_year(self) -> str:
        """'Hyndman (1996)', 'Kruschke & Liddell (2018)', 'Lakens et al. (2018)'.

        Derived from the citation so it cannot drift from it. A citation with
        no year in brackets -- documentation, say -- gives its first element.
        """
        match = _CITE_AUTHORS_YEAR.match(self.cite)
        if not match:
            return self.cite.split(".")[0].strip() or self.cite
        authors, year = match.group("authors").strip(), match.group("year")
        first = authors.split(",")[0].strip()
        if "et al" in authors:
            names = f"{first} et al."
        elif "&" in authors:
            before, after = authors.split("&", 1)
            if _AUTHOR_BOUNDARY.search(before.rstrip(" ,")):
                names = f"{first} et al."
            else:
                names = f"{first} & {after.strip().split(',')[0].strip()}"
        else:
            names = first
        return f"{names} ({year})"

    def access_label(self) -> str:
        return ACCESS_LABELS.get(self.access, "")

    def read_link(self) -> str:
        """A free copy where one was found, otherwise the DOI or URL."""
        return self.access_url or self.link()

    def to_dict(self) -> Dict[str, str]:
        return {
            "cite": self.cite,
            "supports": self.supports,
            "doi": self.doi,
            "url": self.url,
            "isbn": self.isbn,
            "checked": self.checked,
            "link": self.link(),
            "short": self.short or self.supports,
            "type": self.type,
            "author_year": self.author_year(),
            "access": self.access,
            "access_label": self.access_label(),
            "access_url": self.access_url,
            "access_checked": self.access_checked,
            "read_link": self.read_link(),
        }


def parse_references_block(body: str, where: str = "") -> List[Reference]:
    """Parse the body of one references block, strictly.

    Strict because a typo in a key -- "suports:" -- would otherwise drop the
    scope statement silently, and the scope statement is what stops a real
    source being read as support for a claim it does not make.
    """
    records: List[Dict[str, str]] = []
    for number, line in enumerate(body.splitlines(), start=1):
        if not line.strip():
            continue
        if line.startswith("- "):
            records.append({})
            line = line[2:]
        elif line.startswith("  ") and records:
            line = line.strip()
        else:
            raise ReferenceFormatError(
                f"{where}: line {number} of a references block is neither a "
                f"new entry ('- cite: ...') nor an indented field: {line!r}")
        key, sep, value = line.partition(":")
        key = key.strip().lower()
        if not sep or key not in REFERENCE_KEYS:
            raise ReferenceFormatError(
                f"{where}: unknown field {key!r} in a references block; "
                f"allowed fields are {', '.join(REFERENCE_KEYS)}")
        if key in records[-1]:
            raise ReferenceFormatError(
                f"{where}: field {key!r} appears twice in one entry")
        records[-1][key] = value.strip()

    out: List[Reference] = []
    for record in records:
        cite = record.get("cite", "")
        if not cite:
            raise ReferenceFormatError(f"{where}: an entry has no cite field")
        if not record.get("supports"):
            raise ReferenceFormatError(
                f"{where}: {cite[:60]!r} has no supports field; say what the "
                f"source is listed for")
        if not (record.get("doi") or record.get("url") or record.get("isbn")):
            raise ReferenceFormatError(
                f"{where}: {cite[:60]!r} has no doi, url or isbn; a reader "
                f"must be able to find it")
        access = record.get("access", "").lower()
        if access:
            if access not in ACCESS_LABELS:
                raise ReferenceFormatError(
                    f"{where}: {cite[:60]!r} has access {access!r}; allowed "
                    f"values are {', '.join(ACCESS_LABELS)}")
            if not record.get("access_checked"):
                raise ReferenceFormatError(
                    f"{where}: {cite[:60]!r} records access without "
                    f"access_checked; say when and against what it was checked")
            if access in ("repository", "author-copy") and not record.get("access_url"):
                raise ReferenceFormatError(
                    f"{where}: {cite[:60]!r} is a free copy but has no access_url")
        doi = record.get("doi", "")
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix):]
        out.append(Reference(
            cite=cite,
            supports=record["supports"],
            doi=doi.strip(),
            url=record.get("url", ""),
            isbn=record.get("isbn", ""),
            checked=record.get("checked", ""),
            short=record.get("short", ""),
            type=record.get("type", ""),
            access=access,
            access_url=record.get("access_url", ""),
            access_checked=record.get("access_checked", ""),
        ))
    return out


def extract_references(
    text: str,
    where: str = "",
) -> Tuple[str, List[Reference], Dict[str, List[Reference]], List[str]]:
    """Split a note into indexable text and its curated references.

    Returns (text without reference blocks, note-level references,
    section-level references keyed by cleaned heading, format errors). A
    malformed block is reported and skipped rather than raised, so one bad
    entry cannot take Academic Chat down; tests/test_reviewer_note_references.py
    fails on any error, so it cannot go unnoticed either.
    """
    headings = [
        (m.start(), m.group(2).strip(" #*"))
        for m in _HEADING.finditer(text)
    ]
    note_refs: List[Reference] = []
    section_refs: Dict[str, List[Reference]] = {}
    errors: List[str] = []
    spans: List[Tuple[int, int]] = []
    references_section_end: Dict[int, int] = {}

    for block in _REFERENCE_BLOCK.finditer(text):
        owner_start, owner = -1, ""
        for start, heading in headings:
            if start < block.start():
                owner_start, owner = start, heading
        spans.append((block.start(), block.end()))
        label = f"{where} [{owner or 'top of note'}]"
        try:
            refs = parse_references_block(block.group("body"), label)
        except ReferenceFormatError as exc:
            errors.append(str(exc))
            continue
        if not owner or owner.strip().lower() == REFERENCES_HEADING:
            note_refs.extend(refs)
            if owner_start >= 0:
                references_section_end[owner_start] = block.end()
        else:
            section_refs.setdefault(owner, []).extend(refs)

    # A "References" section is a list, not guidance: drop its heading and
    # introduction along with the blocks, but leave whatever follows the last
    # block (the note's "Based on" line) attached to the section before it,
    # exactly as it was before references existed.
    for start, end in references_section_end.items():
        spans.append((start, end))

    if not spans:
        return text, note_refs, section_refs, errors

    spans.sort()
    merged: List[Tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    pieces, cursor = [], 0
    for start, end in merged:
        pieces.append(text[cursor:start])
        # A block sits between blank lines; take one of them with it, so the
        # note reads exactly as it did before the block was added.
        if text[:start].endswith("\n\n") and text[end:end + 1] == "\n":
            end += 1
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), note_refs, section_refs, errors


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _sections(text: str) -> List[Tuple[str, str]]:
    """(heading, body) pairs, packed up to CHUNK_CHARS, split if longer."""
    marks = list(_HEADING.finditer(text))
    if len(marks) < 2:
        # A note with no heading structure -- the BARG summary is a single
        # markdown table -- would otherwise become one undiluted blob with no
        # citable heading. Fall back to fixed-size pieces.
        body = text.strip()
        if not body:
            return []
        return [("", body[i:i + CHUNK_CHARS]) for i in range(0, len(body), CHUNK_CHARS)]

    spans = []
    if marks[0].start() > 0:
        spans.append(("", text[:marks[0].start()]))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        spans.append((m.group(2).strip(" #*"), text[m.start():end]))

    out: List[Tuple[str, str]] = []
    pending: List[Tuple[str, str]] = []
    for head, body in spans:
        if not body.strip():
            continue
        if len(body) > CHUNK_CHARS:
            for i in range(0, len(body), CHUNK_CHARS):
                out.append((head, body[i:i + CHUNK_CHARS]))
        elif (len(body) < MIN_SECTION_CHARS and out
              and len(out[-1][1]) + len(body) <= CHUNK_CHARS):
            prev_head, prev_body = out[-1]
            out[-1] = (prev_head, prev_body + body)
        elif len(body) < MIN_SECTION_CHARS and not out:
            # Nothing before it to merge into: hold it and prepend to the next.
            pending.append((head, body))
        else:
            if pending:
                head = pending[0][0] or head
                body = "".join(b for _, b in pending) + body
                pending.clear()
            out.append((head, body))
    if pending:
        out.append((pending[0][0], "".join(b for _, b in pending)))
    return [(h, b.strip()) for h, b in out if b.strip()]


def _tokenise(text: str) -> List[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def is_meta(note: str, heading: str) -> bool:
    """A section that describes the note rather than answering a question.

    The note's own title counts: the text before the first inner heading is
    the purpose paragraph, and it carries the title as its heading.
    """
    h = heading.strip().lower()
    return h.startswith(META_HEADINGS) or h == note.strip().lower()


def expand(query: str) -> str:
    """Add exact technical synonyms for terms the notes may spell differently."""
    low = query.lower()
    extra = [v for pattern, v in ALIASES.items() if re.search(pattern, low)]
    return query + (" " + " ".join(extra) if extra else "")


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class NotesIndex:
    """
    TF-IDF over the reviewer notes, in memory.

    Smoothed IDF and L2-normalised document vectors, matching the usual
    formulation: idf(t) = ln((1 + N) / (1 + df(t))) + 1. The corpus is a few
    dozen chunks, so building it costs milliseconds and no index file is kept.
    """

    def __init__(self, notes_dir: Path = NOTES_DIR):
        self.notes_dir = Path(notes_dir)
        self.passages: List[Passage] = []
        self._vectors: List[Dict[str, float]] = []
        self._idf: Dict[str, float] = {}
        # Curated references, keyed by the same note title and cleaned
        # heading that passages carry, so a retrieved passage finds its list.
        self.note_references: Dict[str, List[Reference]] = {}
        self.section_references: Dict[Tuple[str, str], List[Reference]] = {}
        self.reference_errors: List[str] = []
        self._build()

    def _build(self) -> None:
        raw: List[Tuple[str, str, str, List[str]]] = []
        for path in sorted(self.notes_dir.glob("*.md")):
            if path.name.upper().startswith("LICEN"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            first = _HEADING.search(text)
            title = first.group(2) if first and first.start() == 0 else path.stem
            title = re.sub(r"[*_`]", "", title).strip()
            if len(title) > 60:
                title = title[:57].rstrip() + "..."
            text, note_refs, section_refs, errors = extract_references(
                text, where=path.name)
            self.reference_errors.extend(errors)
            if note_refs:
                self.note_references[title] = note_refs
            for heading, refs in section_refs.items():
                self.section_references[(title, heading)] = refs
            for heading, body in _sections(text):
                raw.append((title, heading, body, _tokenise(body)))

        n = len(raw)
        df: Dict[str, int] = {}
        for _, _, _, toks in raw:
            for t in set(toks):
                df[t] = df.get(t, 0) + 1
        self._idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}

        for title, heading, body, toks in raw:
            counts: Dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            vec = {t: c * self._idf[t] for t, c in counts.items()}
            norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
            self._vectors.append({t: w / norm for t, w in vec.items()})
            self.passages.append(Passage(title, heading, body, 0.0))

    def references_for(self, note: str, heading: str = "") -> List[Reference]:
        """The curated references for a passage's section, else its note's.

        Empty when neither has any, which most notes will until they are
        curated. A short section merged into the one above it during chunking
        carries that section's heading, and so that section's references.
        """
        section = self.section_references.get((note, heading))
        if section:
            return list(section)
        return list(self.note_references.get(note, []))

    def search(self, query: str, k: int = 3, use_aliases: bool = True) -> List[Passage]:
        q = expand(query) if use_aliases else query
        counts: Dict[str, int] = {}
        for t in _tokenise(q):
            counts[t] = counts.get(t, 0) + 1
        qv = {t: c * self._idf[t] for t, c in counts.items() if t in self._idf}
        norm = math.sqrt(sum(w * w for w in qv.values())) or 1.0
        qv = {t: w / norm for t, w in qv.items()}

        scored: List[Tuple[float, int]] = []
        for i, dv in enumerate(self._vectors):
            if len(qv) < len(dv):
                s = sum(w * dv.get(t, 0.0) for t, w in qv.items())
            else:
                s = sum(w * qv.get(t, 0.0) for t, w in dv.items())
            if s > 0:
                p = self.passages[i]
                if is_meta(p.note, p.heading):
                    s *= META_WEIGHT
                scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], x[1]))

        out = []
        for s, i in scored[:k]:
            p = self.passages[i]
            out.append(Passage(p.note, p.heading, p.text, round(s, 4)))
        return out


def expand_section_siblings(
    passages: List[Passage],
    corpus: List[Passage],
) -> List[Passage]:
    """Recover sibling chunks for retrieved headed sections.

    Long Markdown sections may be split into several passages at CHUNK_CHARS.
    Retrieval ranks those chunks independently. For downstream methodological
    use, recover the remaining chunks of any retrieved headed section so an
    arbitrary chunk boundary does not hide relevant guidance.

    Headingless passages are not expanded because they may be fixed-size
    fallback chunks from an otherwise unstructured note rather than parts of
    one semantic section.
    """
    if not passages:
        return []

    wanted = {
        (p.note, p.heading)
        for p in passages
        if p.heading
    }

    siblings: Dict[Tuple[str, str], List[Passage]] = {}
    for p in corpus:
        key = (p.note, p.heading)
        if p.heading and key in wanted:
            siblings.setdefault(key, []).append(p)

    out: List[Passage] = []
    seen = set()

    for anchor in passages:
        key = (anchor.note, anchor.heading)
        candidates = siblings.get(key, [anchor]) if anchor.heading else [anchor]

        for p in candidates:
            identity = (p.note, p.heading, p.text)
            if identity in seen:
                continue
            seen.add(identity)

            score = anchor.score if p.text == anchor.text else 0.0
            out.append(Passage(p.note, p.heading, p.text, score))

    return out



# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------

def format_passages(passages: List[Passage], limit_chars: int = 700) -> str:
    """
    Render the passages for a chat answer.

    Deliberately headed as reading rather than as an answer, and deliberately
    unconditional: the score is not shown and is not used to decide whether to
    display anything, because it does not separate an answerable question from
    an unanswerable one.
    """
    if not passages:
        return ""
    lines = [
        "Passages you may find relevant, from the reviewer notes. These were "
        "retrieved by word overlap with your question; they are not an answer "
        "to it, and one of them may simply be off the point.",
        "",
    ]
    for p in passages:
        body = " ".join(p.text.split())
        if len(body) > limit_chars:
            body = body[:limit_chars].rstrip() + " ..."
        lines.append(f"**{p.cite()}**")
        lines.append(f"> {body}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
