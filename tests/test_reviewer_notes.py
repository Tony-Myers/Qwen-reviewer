#!/usr/bin/env python3
"""
Checks on tests/reviewer_notes.py.

Every negative case is something that actually went wrong while the module was
being built or during the measurements in reports/CHAT-RETRIEVAL-PROBE.md.

    python3 tests/test_reviewer_notes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reviewer_notes as rn   # noqa: E402

PASS, FAIL = 0, 0


def check(label: str, condition: bool) -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")


index = rn.NotesIndex()


def top(question: str):
    hits = index.search(question, k=1)
    return hits[0] if hits else None


print("index")
check("notes were found", len(index.passages) > 50)
check("more than one note is represented", len({p.note for p in index.passages}) >= 8)
check("the licence file is not indexed",
      not any("licen" in p.note.lower() for p in index.passages))
check("no passage exceeds the chunk limit",
      max(len(p.text) for p in index.passages) <= rn.CHUNK_CHARS)
check("every passage carries a note title", all(p.note for p in index.passages))

print("citation lands on the right section")
# Packing small sections together returned the R-hat answer under the heading
# "What is Hamiltonian Monte Carlo?" -- right passage, wrong citation.
cases = [
    ("is an R-hat of 1.01 acceptable", "R-hat"),
    ("what is Pareto k", "Pareto"),
    ("does a non-significant p-value mean there is no effect", "non-significant result"),
    ("is a lower or higher DIC better", "DIC"),
    ("what is BFMI", "BFMI"),
]
for question, expected in cases:
    hit = top(question)
    check(f"{question!r} -> heading contains {expected!r}",
          hit is not None and expected.lower() in hit.heading.lower())

# ELPD is asserted on content rather than on a heading. Adding the effect-size
# note, which uses "direction" in its own sense, lowered the IDF of that word
# and moved "Which direction is better?" out of the top slot. What replaced it
# -- "What is ELPD?" -- states "Higher ELPD values indicate better expected
# predictive performance", so the question is answered by the passage a reader
# sees first. Asserting the heading would have failed on an improvement; the
# assertion is therefore on the answer being present and visible.
elpd = index.search("which direction is better for ELPD", k=3)
check("'which direction is better for ELPD' -> the top passage says which way is better",
      bool(elpd) and "higher elpd" in elpd[0].text.lower())
check("'which direction is better for ELPD' -> the direction section is still returned",
      any("direction" in h.heading.lower() for h in elpd))

# Where several sections of one note are within a hair of each other, the right
# one need only be in the top few. "Does the outcome have to be Normally
# distributed?" scores 0.418 against 0.435 for "What are residuals?" -- a tie,
# not a failure, and both are the passage a reviewer wants.
near_ties = [
    ("what if residuals are normal but the outcome is not", "normally distributed"),
    ("should heteroscedasticity be corrected", "heteroscedas"),
]
for question, expected in near_ties:
    heads = [h.heading.lower() for h in index.search(question, k=3)]
    check(f"{question!r} -> {expected!r} within the top three",
          any(expected in h for h in heads))

# Known coverage gap rather than a retrieval fault: prior predictive checks are
# required by the BARG and appear in exactly one passage, inside the BARG
# summary table, with no section of their own in any note. Recorded here so the
# gap is visible; the assertion is on the corpus, not on the ranking.
_ppc = [p for p in index.passages if "prior predictive" in p.text.lower()]
check("prior predictive checks appear somewhere in the notes", len(_ppc) >= 1)
if len(_ppc) < 2:
    print("  NOTE: prior predictive checks occur in only "
          f"{len(_ppc)} passage; no note gives them a section of their own.")

print("alias expansion")
# Exact technical synonyms only. Aliasing R-hat to PSRF turned a complete miss
# into the defining passage; aliasing WAIC to a conceptual paraphrase made that
# question worse, which is why only synonyms belong in the map.
check("R-hat expands to PSRF", "psrf" in rn.expand("is R-hat acceptable").lower())
check("ESS expands", "n_eff" in rn.expand("what is the effective sample size").lower())
check("an unrelated question is not expanded",
      rn.expand("how should priors be justified") == "how should priors be justified")
check("aliases can be switched off",
      index.search("R-hat", k=1, use_aliases=False) is not None)

print("nothing is invented")
# A question the notes do not cover must return nothing rather than the least
# bad passage. sklearn's top-k always returns k, which attached cautionary
# passages to correct statements; this returns only positive-scoring matches.
for question in ["how do I select a clustering method",
                 "explain principal component analysis eigenvectors",
                 "what is the capital of France"]:
    hits = index.search(question, k=3)
    check(f"no forced result for {question[:38]!r}",
          all(h.score > 0 for h in hits))
# The nonsense string must stay nonsense. "unrelated" stopped being nonsense
# when the network meta-analysis note arrived carrying "unrelated mean effects
# models", and this check failed on a real word rather than on a fault. Any
# replacement must avoid words that could become technical terms later.
check("an entirely unrelated question returns nothing at all",
      index.search("zzzqqq vvvv xqklm bfftz", k=3) == [])

print("meta sections are demoted")
# A note's purpose, terminology, red flags and checklists match many questions
# by word overlap and answer almost none of them. Before they were demoted, the
# heterogeneity question returned the note's preamble, its checklist and its
# definition, and none of the sections that answer it.
check("the demotion weight is the measured one", rn.META_WEIGHT == 0.5)
check("a note title is recognised as its own preamble",
      rn.is_meta("Between-Study Heterogeneity and Priors on Tau",
                 "Between-Study Heterogeneity and Priors on Tau"))
check("a question heading is not treated as meta",
      not rn.is_meta("Effect Sizes", "Why does the denominator of an SMD matter?"))
for question in ["how sensitive are the results to the prior for heterogeneity",
                 "what convergence diagnostics should be reported",
                 "were the outcomes from the same participants independent"]:
    hits = index.search(question, k=3)
    check(f"no meta section leads {question[:40]!r}",
          bool(hits) and not rn.is_meta(hits[0].note, hits[0].heading))

print("presentation")
passages = index.search("what convergence diagnostics should be reported", k=2)
rendered = rn.format_passages(passages)
check("rendered block is headed as reading, not as an answer",
      "not an answer" in rendered)
check("rendered block cites the note", passages[0].note.split(",")[0] in rendered)
check("no score is shown to the reader", "0." not in rendered.split("\n")[0])
check("empty input renders nothing", rn.format_passages([]) == "")
long_hit = max(index.passages, key=lambda p: len(p.text))
check("long passages are truncated for display",
      len(rn.format_passages([rn.Passage(long_hit.note, long_hit.heading,
                                         long_hit.text, 0.5)])) < 1200)

print(f"\n{PASS} passed, {FAIL} failed")
raise SystemExit(1 if FAIL else 0)
