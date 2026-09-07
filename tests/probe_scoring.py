#!/usr/bin/env python3
"""
Should the scorer saturate term frequency and normalise by passage length?

Diagnosed in section 12.8 of reports/CHAT-RETRIEVAL-PROBE.md. Raw term
frequency with L2 normalisation rewards density, so a short list-like section
outranks a longer explanatory one whenever they share a common word:

    query: why might a placebo test for coach effects lack statistical precision?
    0.1477  Can a missing SD be reconstructed?   test 0.4002  (585 chars)
    0.1367  What do placebo tests establish?     test 0.3102, placebo 0.0850

Three instances of that pattern are on record. BM25 is the standard remedy: a
fourth occurrence of "test" adds almost nothing, and length is normalised
against the mean rather than by the vector norm.

    python3 tests/probe_scoring.py

BM25 scores are not cosines, so medians cannot be compared across scorers. The
headline is rank separation: the probability that a randomly chosen in-scope
question outscores a randomly chosen out-of-scope one, which is invariant to
any monotone rescaling. Ties count a half. The held-out counts are rank-based
and comparable as they stand.
"""

import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reviewer_notes as rn                       # noqa: E402
from run_reviewer_notes import QUESTIONS          # noqa: E402
from probe_expansion import MANUSCRIPT            # noqa: E402

INDEX = rn.NotesIndex()
DOCS = [rn._tokenise(p.text) for p in INDEX.passages]
N = len(DOCS)
AVGDL = sum(len(d) for d in DOCS) / N

DF = {}
for d in DOCS:
    for t in set(d):
        DF[t] = DF.get(t, 0) + 1

# The shipped weighting, kept so the current behaviour is one of the arms.
IDF_SMOOTH = {t: math.log((1 + N) / (1 + df)) + 1.0 for t, df in DF.items()}
# BM25's own, which goes negative for terms in more than half the passages --
# floored, as implementations normally do, so a very common word cannot
# subtract from a match.
IDF_BM25 = {t: max(0.0, math.log((N - df + 0.5) / (df + 0.5) + 1.0))
            for t, df in DF.items()}

COUNTS = []
for d in DOCS:
    c = {}
    for t in d:
        c[t] = c.get(t, 0) + 1
    COUNTS.append(c)

# L2-normalised tf-idf vectors, as shipped.
VECS = []
for c in COUNTS:
    v = {t: n * IDF_SMOOTH[t] for t, n in c.items()}
    norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
    VECS.append({t: w / norm for t, w in v.items()})


def score_cosine(qt):
    counts = {}
    for t in qt:
        counts[t] = counts.get(t, 0) + 1
    qv = {t: n * IDF_SMOOTH[t] for t, n in counts.items() if t in IDF_SMOOTH}
    norm = math.sqrt(sum(w * w for w in qv.values())) or 1.0
    qv = {t: w / norm for t, w in qv.items()}
    return [sum(w * dv.get(t, 0.0) for t, w in qv.items()) for dv in VECS]


def make_bm25(k1, b, idf):
    def score(qt):
        out = []
        for c, d in zip(COUNTS, DOCS):
            dl = len(d)
            s = 0.0
            for t in set(qt):
                f = c.get(t, 0)
                if not f:
                    continue
                s += idf.get(t, 0.0) * (f * (k1 + 1)) / (
                    f + k1 * (1 - b + b * dl / AVGDL))
            out.append(s)
        return out
    return score


def ranked(scorer, question, k=3):
    qt = rn._tokenise(rn.expand(question))
    scores = scorer(qt)
    rows = []
    for i, s in enumerate(scores):
        if s <= 0:
            continue
        p = INDEX.passages[i]
        if rn.is_meta(p.note, p.heading):
            s *= rn.META_WEIGHT
        rows.append((s, i))
    rows.sort(key=lambda x: (-x[0], x[1]))
    return [(s, INDEX.passages[i]) for s, i in rows[:k]]


def auc(ins, out):
    """P(a random in-scope question outscores a random out-of-scope one)."""
    wins = sum(1 for a in ins for b in out if a > b)
    ties = sum(1 for a in ins for b in out if a == b)
    return (wins + 0.5 * ties) / (len(ins) * len(out))


def evaluate(scorer):
    ins, out = [], []
    for flag, q in QUESTIONS:
        hits = ranked(scorer, q, k=1)
        (ins if flag else out).append(hits[0][0] if hits else 0.0)
    top = top3 = 0
    for note_set, q in MANUSCRIPT:
        hits = ranked(scorer, q, k=3)

        def good(p):
            return (any(n in p.note for n in note_set)
                    and not rn.is_meta(p.note, p.heading))
        if hits and good(hits[0][1]):
            top += 1
        if any(good(p) for _, p in hits):
            top3 += 1
    return auc(ins, out), statistics.median(ins), statistics.median(out), top, top3


# The diagnosis in 12.8 was about the document side: density in a short passage.
# BM25 changes the query side too, dropping the normalisation that stops a long
# out-of-scope question accumulating score across several common words. These
# arms keep cosine and change only what was diagnosed.

def make_cosine_damped(damp):
    vecs = []
    for c in COUNTS:
        v = {t: damp(n) * IDF_SMOOTH[t] for t, n in c.items()}
        norm = math.sqrt(sum(w * w for w in v.values())) or 1.0
        vecs.append({t: w / norm for t, w in v.items()})

    def score(qt):
        counts = {}
        for t in qt:
            counts[t] = counts.get(t, 0) + 1
        qv = {t: damp(n) * IDF_SMOOTH[t] for t, n in counts.items()
              if t in IDF_SMOOTH}
        norm = math.sqrt(sum(w * w for w in qv.values())) or 1.0
        qv = {t: w / norm for t, w in qv.items()}
        return [sum(w * dv.get(t, 0.0) for t, w in qv.items()) for dv in vecs]
    return score


def saturate(k1):
    return lambda n: (n * (k1 + 1)) / (n + k1)


DIAGNOSTIC = [
    "Why might a placebo test for coach effects lack statistical precision?",
    "Should authors justify the alpha level or significance threshold they chose?",
    "Are Cohen's 0.2, 0.5 and 0.8 conventions justified for this population?",
]

ARMS = [
    ("A  tf-idf cosine  (ships)", score_cosine),
    ("B  BM25  k1=1.2 b=0.75", make_bm25(1.2, 0.75, IDF_BM25)),
    ("C  BM25  k1=1.2 b=0.50", make_bm25(1.2, 0.50, IDF_BM25)),
    ("D  BM25  k1=1.2 b=0.00", make_bm25(1.2, 0.00, IDF_BM25)),
    ("E  BM25  k1=1.2 b=0.75, smoothed idf", make_bm25(1.2, 0.75, IDF_SMOOTH)),
    ("F  BM25  k1=0.5 b=0.75", make_bm25(0.5, 0.75, IDF_BM25)),
    ("G  cosine, saturated tf  k1=1.2", make_cosine_damped(saturate(1.2))),
    ("H  cosine, saturated tf  k1=0.5", make_cosine_damped(saturate(0.5))),
    ("I  cosine, log tf", make_cosine_damped(lambda n: 1.0 + math.log(n))),
]


def main() -> int:
    print(f"{N} passages, mean length {AVGDL:.0f} tokens\n")
    print(f"{'arm':<38}{'sep':>7}{'in':>9}{'out':>8}{'top':>8}{'top-3':>8}")
    print("-" * 78)
    for label, scorer in ARMS:
        sep, m_in, m_out, top, top3 = evaluate(scorer)
        print(f"{label:<38}{sep:>7.3f}{m_in:>9.3f}{m_out:>8.3f}"
              f"{top:>5} /10{top3:>5} /10")

    print("""
sep is the rank separation: the probability that a randomly chosen in-scope
question outscores a randomly chosen out-of-scope one. It is the only column
comparable across scorers, since BM25 scores are not cosines. in and out are
the medians, readable within an arm but not across arms. top and top-3 are the
ten questions from a live review, as in probe_expansion.py.
""")
    print("The three queries that motivated this, leading passage per arm:\n")
    for q in DIAGNOSTIC:
        print(f"  {q}")
        for label, scorer in ARMS:
            hits = ranked(scorer, q, k=1)
            head = hits[0][1].heading[:50] if hits else "(nothing)"
            print(f"      {label:<38} {head}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
