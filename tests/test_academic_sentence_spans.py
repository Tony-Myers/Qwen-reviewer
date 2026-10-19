#!/usr/bin/env python3
"""
Sentence boundaries in Academic Chat answers.

    python3 tests/test_academic_sentence_spans.py

answer_sentence_spans is shared by claim decomposition, the per-sentence
discovery audit, the source context given to the methodology judge and
reconciliation, and the answer sentences the evidence check quotes. It used
to end a sentence at every full stop followed by a space, so "i.e. the
central 95%" or "ETI vs. HDI" was cut in two, and a claim quoted across that
cut could not be placed in one sentence (the Academic Chat 500).

Checked: the five abbreviations no longer split; "et al." still splits when
it ends a sentence; ordinary boundaries, look-alike words, decimals, and the
existing behaviour pinned in test_academic_claim_coverage [39] are unchanged.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import academic_claim_coverage as coverage  # noqa: E402

failures = 0


def check(condition, label):
    global failures
    print(("PASS: " if condition else "FAIL: ") + label)
    if not condition:
        failures += 1


def sentences(text):
    return [text[a:b] for a, b in coverage.answer_sentence_spans(text)]


def one_sentence(text, label):
    got = sentences(text)
    check(got == [text], f"{label}: one sentence" + ("" if got == [text] else f" -> {got}"))


print("\n[1] abbreviations inside a sentence do not end it")
one_sentence("The ETI uses fixed percentiles, i.e. the central 95% of draws.", "i.e.")
one_sentence("A skewed posterior, e.g. a variance, separates the two intervals.", "e.g.")
one_sentence("The 95% ETI vs. HDI choice matters for skewed posteriors.", "vs. before a capital")
one_sentence("The ETI vs. the HDI differ under skew.", "vs. before lower case")
one_sentence("Interval choice changes the bounds (cf. Kruschke, 2015).", "cf.")
one_sentence("This was shown by Makowski et al. (2019) for credible intervals.", "et al. before a bracket")
one_sentence("Makowski et al. 2019 compared both intervals.", "et al. before a year")
one_sentence("Makowski et al. compared both intervals.", "et al. before lower case")
one_sentence("Upper case forms also apply, I.E. the central region, E.G. a rate.", "upper-case forms")

print("\n[2] the following sentence still starts where it should")
text = ("An ETI cuts 2.5% from each tail, i.e. it is equal-tailed. "
        "An HDI holds the most probable values.")
check(sentences(text) == [
    "An ETI cuts 2.5% from each tail, i.e. it is equal-tailed.",
    "An HDI holds the most probable values."],
    "two real sentences give two spans")

text = "This was described by Kruschke et al. The HDI is then the shortest interval."
check(sentences(text) == [
    "This was described by Kruschke et al.",
    "The HDI is then the shortest interval."],
    "et al. ending a sentence still splits before a capital")

text = "Neither is wrong, e.g. both are valid. Choose one in advance."
check(len(sentences(text)) == 2, "an abbreviation does not swallow the next real boundary")

print("\n[3] unrelated boundary behaviour is unchanged")
check(sentences("We tested three TVs. The ETI was wide.") ==
      ["We tested three TVs.", "The ETI was wide."],
      "a word ending in 'vs' is not mistaken for vs.")
check(sentences("The p value was .05. The HDI was 0.2 to 1.4.") ==
      ["The p value was .05.", "The HDI was 0.2 to 1.4."],
      "decimals are untouched")
check(sentences("Is it skewed? Yes! Then the intervals differ.") ==
      ["Is it skewed?", "Yes!", "Then the intervals differ."],
      "question and exclamation marks still end sentences")
check(sentences("First statistical proposition. Second methodological "
                "proposition! Third proposition without terminal punctuation") ==
      ["First statistical proposition.", "Second methodological proposition!",
       "Third proposition without terminal punctuation"],
      "the behaviour pinned in test_academic_claim_coverage [39] is unchanged")
check(sentences("Both intervals are valid, e.g.") == ["Both intervals are valid, e.g."],
      "an abbreviation at the very end leaves one sentence")
check(sentences("") == [] and sentences("   ") == [], "empty text gives no spans")
check(sentences("No punctuation at all") == ["No punctuation at all"],
      "text without a stop is one sentence")

print("\n[4] a claim quoted across an abbreviation now resolves to its sentence")
draft = ("An equal-tailed interval uses the 2.5th and 97.5th percentiles, i.e. "
         "it cuts 2.5% from each tail. The highest density interval contains "
         "the most probable values.")
anchor = "97.5th percentiles, i.e. it cuts 2.5% from each tail"
start = draft.index(anchor)
context = coverage.resolve_claim_source_context(
    answer_draft=draft, source_start=start, source_end=start + len(anchor))
check(context.source_sentence == (
    "An equal-tailed interval uses the 2.5th and 97.5th percentiles, i.e. "
    "it cuts 2.5% from each tail."), "the whole sentence is the source sentence")

print()
print("All checks passed." if not failures else f"{failures} check(s) FAILED.")
sys.exit(1 if failures else 0)
