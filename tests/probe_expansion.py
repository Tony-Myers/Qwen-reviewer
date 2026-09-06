#!/usr/bin/env python3
"""
Why meta-section demotion ships, and why word-form folding and query expansion
do not.

Design note 5 in reviewer_notes.py rests on this comparison. It is kept so the
comparison can be repeated: the notes change, and a conclusion drawn over
fifteen of them is not automatically true over twenty.

    python3 tests/probe_expansion.py

Five arms over the fifty-one labelled questions, plus ten questions taken from
a live manuscript review and held outside the tuning loop:

    A  no demotion                  what the module did before design note 5
    B  no demotion + folding        suffix folding, notes and query alike
    C  no demotion + folding + concept   B, and "sensitivity" also matches
                                    "robust(ness)"
    D  demotion                     what ships
    E  demotion + folding

The question is NOT whether the question about the prior on tau improves. That
question motivated the change, so any expansion wide enough will fix it. What
matters is the gap between the in-scope and out-of-scope medians, because the
value of the notes rests on their not answering what they do not cover.
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reviewer_notes as rn                       # noqa: E402
from run_reviewer_notes import QUESTIONS          # noqa: E402

# Folding these would merge distinctions the notes rely on: "consistency" is a
# technical term in the network meta-analysis note, and prediction intervals,
# predictive performance and posterior predictive checks are three different
# things living in three different notes.
PROTECTED = {"consistency", "consistent", "prediction", "predictions",
             "predictive", "predict", "predicting"}

# First match wins. Deliberately small: a hand rule set is what can stay in the
# standard library, and its crudeness is part of what is being measured.
RULES = [("ies", "y"), ("ness", ""), ("ity", ""), ("ing", ""),
         ("ed", ""), ("es", ""), ("ly", ""), ("s", ""), ("e", "")]

CONCEPT = {"sensitiv": "robust", "robust": "sensitiv"}


def fold(tok: str) -> str:
    if tok in PROTECTED or len(tok) < 5 or tok.endswith("ss"):
        return tok
    for suf, repl in RULES:
        if tok.endswith(suf):
            base = tok[: len(tok) - len(suf)] + repl
            if len(base) >= 4:
                return base
    return tok


def make_tokeniser(do_fold: bool, do_concept: bool, query_side: bool):
    plain = rn._tokenise

    def tok(text: str):
        out = [fold(t) for t in plain(text)] if do_fold else list(plain(text))
        if do_concept and query_side:
            out += [CONCEPT[t] for t in set(out) if t in CONCEPT]
        return out
    return tok


def build(do_fold: bool):
    """An index whose documents are tokenised the way this arm requires."""
    original = rn._tokenise
    rn._tokenise = make_tokeniser(do_fold, False, query_side=False)
    try:
        return rn.NotesIndex()
    finally:
        rn._tokenise = original


def run(index, do_fold: bool, do_concept: bool, meta_weight: float):
    original_tok, original_w = rn._tokenise, rn.META_WEIGHT
    rn._tokenise = make_tokeniser(do_fold, do_concept, query_side=True)
    rn.META_WEIGHT = meta_weight
    try:
        scores = {}
        for in_scope, q in QUESTIONS:
            hits = index.search(q, k=1)
            scores.setdefault(in_scope, []).append(hits[0].score if hits else 0.0)
        note_ok, sect_ok = [], []
        for note_set, q in MANUSCRIPT:
            hits = index.search(q, k=1)
            right = bool(hits) and any(n in hits[0].note for n in note_set)
            note_ok.append(right)
            # the strict criterion: the right note AND a section that explains
            # something, rather than the note's preamble or its checklist
            sect_ok.append(right and not rn.is_meta(hits[0].note, hits[0].heading))
        return scores, note_ok, sect_ok
    finally:
        rn._tokenise, rn.META_WEIGHT = original_tok, original_w


# Ten questions from a live review of a Bayesian dose-response meta-analysis.
# The allowed notes are the ones that ought to answer each, recorded before the
# arms were run. The list is deliberately strict and one entry is arguably too
# strict: on the first question the Lee and Yin passage on credible versus
# confidence intervals is a good answer from a note not listed here.
MANUSCRIPT = [
    (("Bayesian Decision Rules",), "Is it appropriate to interpret a 95% Bayesian credible "
     "interval that excludes zero as showing statistical significance?"),
    (("Bayesian Decision Rules",), "If the authors use whether the 95% CrI crosses zero as a "
     "decision rule, was that rule prespecified, and why was 95% chosen?"),
    (("Bayesian Decision Rules",), "Should the authors report posterior probabilities such as "
     "P(effect > 0 | data), or probabilities that the effect exceeds a clinically meaningful "
     "threshold, rather than only whether the CrI includes zero?"),
    (("Effect Sizes",), "Are Cohen's 0.2, 0.5 and 0.8 conventions justified for "
     "executive-function outcomes in this population?"),
    (("Effect Sizes",), "Could differences in outcome variability between studies affect the "
     "SMD independently of differences in the underlying treatment effect?"),
    (("Model Fit", "Bayesian Model Comparison", "Dose-Response"), "If DIC was used to select "
     "the dose-response model, was lower DIC correctly interpreted as preferable, and were "
     "differences sufficiently large to support choosing one model over another?"),
    (("Effect Sizes",), "Were multiple executive-function outcomes from the same participants "
     "treated as statistically independent, or was their within-study dependence modelled?"),
    (("Between-Study Heterogeneity",), "How sensitive are the results to the prior for "
     "between-study heterogeneity?"),
    (("Dose-Response",), "Does the network contain enough observations across the dose range "
     "to estimate nonlinearity reliably, particularly at very low and very high doses?"),
    (("HMC", "Bayesian Computation"), "If Stan/HMC was used, were divergent transitions or "
     "other sampler diagnostics reported; if JAGS/WinBUGS was used, how was convergence "
     "established?"),
]

ARMS = [("A  no demotion", False, False, 1.0),
        ("B  no demotion + folding", True, False, 1.0),
        ("C  no demotion + fold + concept", True, True, 1.0),
        ("D  demotion  (ships)", False, False, rn.META_WEIGHT),
        ("E  demotion + folding", True, False, rn.META_WEIGHT)]


def main() -> int:
    print(f"{'arm':<32}{'in-scope':>10}{'out':>8}{'gap':>8}"
          f"{'note':>8}{'section':>10}{'terms':>8}")
    print("-" * 84)
    cache = {}
    for label, do_fold, do_concept, weight in ARMS:
        if do_fold not in cache:
            cache[do_fold] = build(do_fold)
        index = cache[do_fold]
        scores, note_ok, sect_ok = run(index, do_fold, do_concept, weight)
        m_in = statistics.median(scores[1])
        m_out = statistics.median(scores[0])
        print(f"{label:<32}{m_in:>10.3f}{m_out:>8.3f}{m_in - m_out:>8.3f}"
              f"{sum(note_ok):>5} /10{sum(sect_ok):>7} /10{len(index._idf):>8}")

    print("""
in-scope and out are the median score of the best passage, over the 21 questions
the notes are meant to cover and the 30 they are not; gap is the difference, and
is the figure to read. note counts the ten manuscript questions whose top
passage came from a note that ought to answer it. section is the stricter count,
where that passage also explains something rather than being the note's
preamble, terminology list or checklist. terms is the vocabulary size, showing
how much folding merged.

Read across: demotion widens the gap and answers more questions with a section
that explains something. Folding does the opposite -- it reaches the right note
more often and the right section less often. Adding "robust" to a question about
sensitivity moves no ranking at all and lowers every score, because the extra
word lengthens the query vector without matching the passages that should win.""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
