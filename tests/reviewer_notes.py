#!/usr/bin/env python3
"""
Retrieval over the reviewer notes, for the chat.

A reviewer reading a finished report asks a question about how a statistic
should be reported or interpreted. This module returns passages from
`resources/reviewer_notes/` that bear on it. It does not answer the question
and it does not decide anything: the model answers, and these passages let the
reviewer check that answer against something written down.

Standalone in tests/, outside the pipeline fingerprint. Standard library only;
no scikit-learn, so the review pipeline gains no dependency.

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
    r"\bpareto\s*k\b": "pareto k diagnostic psis",
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
                scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], x[1]))

        out = []
        for s, i in scored[:k]:
            p = self.passages[i]
            out.append(Passage(p.note, p.heading, p.text, round(s, 4)))
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
